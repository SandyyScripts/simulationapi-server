import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser
import requests
from geopy.distance import geodesic
from django.views.decorators.csrf import csrf_exempt
from .models import APIUsage
from django.utils import timezone
from django.http import JsonResponse
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

BANGALORE_BOUNDING_BOX = {
    'minLat': 12.834,
    'maxLat': 13.139,
    'minLng': 77.528,
    'maxLng': 77.728,
}

def generate_random_color(exclude_colors=None):
    exclude_colors = exclude_colors or []
    while True:
        color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        if color not in exclude_colors:
            return color

def generate_random_coordinates(n, bounding_box, is_destination=True, exclude_color=None):
    coordinates = []
    for _ in range(n):
        lat = random.uniform(bounding_box['minLat'], bounding_box['maxLat'])
        lng = random.uniform(bounding_box['minLng'], bounding_box['maxLng'])
        color = generate_random_color(exclude_colors=[exclude_color])
        if is_destination:
            destination_lat = random.uniform(bounding_box['minLat'], bounding_box['maxLat'])
            destination_lng = random.uniform(bounding_box['minLng'], bounding_box['maxLng'])
            coordinates.append({
                'source': {'latitude': lat, 'longitude': lng},
                'destination': {'latitude': destination_lat, 'longitude': destination_lng},
                'color': color
            })
        else:
            coordinates.append({
                'latitude': lat,
                'longitude': lng,
                'color': exclude_color
            })
    return coordinates

class RideBookingAPIView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        passengers = request.data.get('passengers')
        rides = request.data.get('rides')
        
        if not passengers or not rides:
            return Response({
                'error': 'Both passengers and rides must be provided.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            passengers = int(passengers)
            rides = int(rides)
        except ValueError:
            return Response({
                'error': 'Passengers and rides must be integers.'
            }, status=status.HTTP_400_BAD_REQUEST)

        passenger_coords = generate_random_coordinates(passengers, BANGALORE_BOUNDING_BOX, is_destination=True, exclude_color='#FFFF00')
        ride_coords = generate_random_coordinates(rides, BANGALORE_BOUNDING_BOX, is_destination=False, exclude_color='#FFFF00')

        passengers_object = {
            f'passenger_{i+1}': passenger_coords[i] for i in range(passengers)
        }
        ride_object = {
            f'ride_{i+1}': ride_coords[i] for i in range(rides)
        }

        return Response({
            'passengers': passengers_object,
            'ride_coordinates': ride_object,
        }, status=status.HTTP_200_OK)
    
class RideSimulatorAPIView(APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        data = request.data

        if 'passengers' not in data or 'ride_coordinates' not in data:
            return Response({
                'error': 'Passengers and ride_coordinates must be provided.'
            }, status=status.HTTP_400_BAD_REQUEST)

        passengers = data['passengers']
        ride_coordinates = data['ride_coordinates']

        # Assign passengers to rides
        assigned_routes, idle_passengers, idle_rides = assign_passengers_to_rides(passengers, ride_coordinates)

        response = {
            'assigned_routes': assigned_routes,
            'idle_passengers': idle_passengers,
            'idle_rides': idle_rides
        }

        return Response(response, status=status.HTTP_200_OK)


def assign_passengers_to_rides(passengers, ride_coordinates):
    passenger_list = list(passengers.items())
    ride_list = list(ride_coordinates.items())

    assigned_routes = []
    idle_passengers = []
    idle_rides = []

    while passenger_list and ride_list:
        ride_key, ride = ride_list.pop(0)
        closest_passenger_key, closest_passenger = min(passenger_list, key=lambda p: calculate_distance(ride, p[1]['source']))
        passenger_list.remove((closest_passenger_key, closest_passenger))

        ride_to_passenger_route = get_direction_route(ride, closest_passenger['source'])
        passenger_source_to_destination_route = get_direction_route(closest_passenger['source'], closest_passenger['destination'])

        assigned_routes.append({
            'passenger_name': closest_passenger_key,
            'route_color': closest_passenger['color'],
            'ride_name': ride_key,
            'ride_to_passenger_route': ride_to_passenger_route,
            'ride_passenger_source_to_destination': passenger_source_to_destination_route
        })

    for passenger_key, passenger in passenger_list:
        idle_passengers.append(passenger_key)

    for ride_key, ride in ride_list:
        idle_rides.append(ride_key)

    return assigned_routes, idle_passengers, idle_rides


def calculate_distance(coord1, coord2):
    return geodesic((coord1['latitude'], coord1['longitude']), (coord2['latitude'], coord2['longitude'])).meters


def get_direction_route(start, end):
    MAP_BOX_ROUTE_ENDPOINT = "https://api.mapbox.com/directions/v5/mapbox/driving"
    coordinates = f"{start['longitude']},{start['latitude']};{end['longitude']},{end['latitude']}"
    access_token = os.environ.get('MAP_BOX_ACCESS_TOKEN')
    url = f"{MAP_BOX_ROUTE_ENDPOINT}/{coordinates}?overview=full&geometries=geojson&access_token={access_token}"

    try:
        res = requests.get(url, headers={"content-type": "application/json"})
        data = res.json()
        return data
    except Exception as error:
        print("Error fetching directions:", error)
        return {}
    

@csrf_exempt
def rate_limited_view(request):
    try:
        usage = APIUsage.objects.first()
        if not usage:
            usage = APIUsage()
            usage.save()

        usage.reset_if_necessary()

        if usage.request_count >= 1000:
            return JsonResponse({'error': 'Limit Exceeded'}, status=429)

        usage.request_count += 1
        usage.save()
        
        return JsonResponse({'message': 'Request successful', 'request_count': usage.request_count})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)