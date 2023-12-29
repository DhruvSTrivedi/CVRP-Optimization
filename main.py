import pandas as pd
import requests
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import folium
import matplotlib.pyplot as plt

# Function to create distance matrix using Google's Distance Matrix API
def create_distance_matrix(locations, api_key):
    addresses = ['{},{}'.format(loc[0], loc[1]) for loc in locations]
    max_elements = 100
    num_addresses = len(addresses)
    max_rows = max(1, min(max_elements // num_addresses, num_addresses))
    q, r = divmod(num_addresses, max_rows)
    distance_matrix = []

    for i in range(q):
        origin_addresses = addresses[i * max_rows: (i + 1) * max_rows]
        response = send_request(origin_addresses, addresses, api_key)
        distance_matrix += build_distance_matrix(response)

    if r > 0:
        origin_addresses = addresses[q * max_rows: q * max_rows + r]
        response = send_request(origin_addresses, addresses, api_key)
        distance_matrix += build_distance_matrix(response)

    return distance_matrix

# Function to send request to Google API
def send_request(origin_addresses, dest_addresses, api_key):
    request = 'https://maps.googleapis.com/maps/api/distancematrix/json?units=metric'
    origin_address_str = '|'.join(origin_addresses)
    dest_address_str = '|'.join(dest_addresses)
    request += '&origins={}&destinations={}&key={}'.format(origin_address_str, dest_address_str, api_key)
    response = requests.get(request)
    return response.json()

# Function to build distance matrix from API response
def build_distance_matrix(response):
    distance_matrix = []
    for row in response['rows']:
        row_list = [element['distance']['value'] for element in row['elements']]
        distance_matrix.append(row_list)
    return distance_matrix

# Function to create data model for the routing problem
def create_data_model(locations, vehicle_count):
    data = {}
    data['locations'] = locations
    data['num_vehicles'] = vehicle_count
    data['depot'] = 0
    data['vehicle_capacities'] = [6] * vehicle_count
    return data

# Function to print solution on console
def print_solution(data, manager, routing, solution):
    total_distance = 0
    total_load = 0
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        plan_output = 'Route for vehicle {}:\n'.format(vehicle_id)
        route_distance = 0
        route_load = 0
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += 1
            plan_output += ' {} ->'.format(node_index)
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
        plan_output += ' {}\n'.format(manager.IndexToNode(index))
        plan_output += 'Distance of the route: {}m\n'.format(route_distance)
        plan_output += 'Load of the route: {}\n'.format(route_load)
        print(plan_output)
        total_distance += route_distance
        total_load += route_load
    print('Total distance of all routes: {}m'.format(total_distance))
    print('Total load of all routes: {}'.format(total_load))

# Function to plot routes on map using Folium with distinct markers and arrows
def plot_routes_on_map(data, manager, routing, solution, depot_location):
    map = folium.Map(location=depot_location, zoom_start=12)
    colors = ['blue', 'green', 'red', 'purple', 'orange']
    # Mark the depot location with a distinct marker
    folium.Marker(depot_location, popup='Depot', icon=folium.Icon(color='black', icon='home')).add_to(map)

    for vehicle_id in range(data['num_vehicles']):
        route_points = [depot_location]
        index = routing.Start(vehicle_id)
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            next_index = solution.Value(routing.NextVar(index))
            if not routing.IsEnd(next_index):
                next_node_index = manager.IndexToNode(next_index)
                # Calculate direction
                direction = calculate_direction(data['locations'][node_index], data['locations'][next_node_index])
                # Add arrow icon
                folium.RegularPolygonMarker(location=data['locations'][node_index], number_of_sides=3, radius=5, rotation=direction, color=colors[vehicle_id % len(colors)], fill_color=colors[vehicle_id % len(colors)]).add_to(map)
            route_points.append(data['locations'][node_index])
            index = next_index
        route_points.append(depot_location)
        folium.PolyLine(route_points, color=colors[vehicle_id % len(colors)], weight=2.5, opacity=1).add_to(map)

    return map

# Function to calculate direction between two points
def calculate_direction(point1, point2):
    import math
    lat1, lon1 = point1
    lat2, lon2 = point2
    angle = math.atan2(lat2 - lat1, lon2 - lon1)
    return math.degrees(angle) + 90  # Adjusting for the icon's orientation

def plot_routes(data, manager, routing, solution):
    plt.figure(figsize=(10, 10))
    markers = ['o', 'v', '^', '<', '>']
    colors = ['blue', 'green', 'red', 'purple', 'orange']

    # Collect all longitudes and latitudes
    all_longs = [loc[1] for loc in data['locations']]
    all_lats = [loc[0] for loc in data['locations']]

    # Distinct marker for the depot
    depot = data['locations'][data['depot']]
    plt.plot(depot[1], depot[0], 'X', markersize=15, color='gold', label='Depot')

    for vehicle_id in range(data['num_vehicles']):
        x = []
        y = []
        index = routing.Start(vehicle_id)
        while True:
            node_index = manager.IndexToNode(index)
            x.append(data['locations'][node_index][1])  # Longitude
            y.append(data['locations'][node_index][0])  # Latitude
            if routing.IsEnd(index):
                break
            index = solution.Value(routing.NextVar(index))
        # Adding the depot coordinates at the end to close the loop
        x.append(depot[1])
        y.append(depot[0])
        plt.plot(x, y, marker=markers[vehicle_id % len(markers)], linestyle='-', color=colors[vehicle_id % len(colors)], markersize=5, label=f'Route {vehicle_id}')
    
    # Plot all nodes
    plt.scatter(all_longs, all_lats, color='gray', zorder=2)

    # Enhance the depot node
    plt.scatter(depot[1], depot[0], color='gold', s=100, edgecolors='black', zorder=3)

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Vehicle Routes')
    plt.xlim(min(all_longs) - 0.01, max(all_longs) + 0.01)  # Adjusting x-axis limits
    plt.ylim(min(all_lats) - 0.01, max(all_lats) + 0.01)  # Adjusting y-axis limits
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


# Main function where the program execution starts
def main():
    # Load dataset
    df = pd.read_csv('/Users/dhruvtrivedi/Downloads/filtered_orders_2022-01-08.csv')
    locations = df[['Latitude', 'Longitude']].values.tolist()[:20]
    depot_location = (43.47930404525, -80.5376428062698)
    locations.insert(0, depot_location)

    # Create distance matrix
    api_key = '**********************' 
    distance_matrix = create_distance_matrix(locations, api_key)

    # Create data model
    data = create_data_model(locations, 5)
    data['distance_matrix'] = distance_matrix

    # Create routing index manager and model
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']), data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    # Define distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['distance_matrix'][from_node][to_node]
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add capacity constraints
    def demand_callback(from_index):
        return 1  # Assuming each delivery has a demand of 1 unit
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')

    # Set parameters for search
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    # Solve the problem
    solution = routing.SolveWithParameters(search_parameters)

    # Print solution and plot routes if a solution is found
    if solution:
        print_solution(data, manager, routing, solution)
        map = plot_routes_on_map(data, manager, routing, solution, depot_location)
        map.save('routes_map.html')
        plot_routes(data, manager, routing, solution)

if __name__ == '__main__':
    main()
