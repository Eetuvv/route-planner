This is backend implementation for university project.

# Route-planner

Route planner uses MQTT client and OpenRouteService API. MQTT client listens for incoming route requests, gets the coordinates from the request, fetches the route from the API and sends the route object back as a response.

## Accident avoidance

Additionally, route planner avoids accidents automatically. It fetches accident data from Mock API, checks if the accident is on the requested route, and if so it creates polygons from the accident areas and passes them to API call to avoid them.

## Dynamic route update

Route planner continuously fetches new accident data in the background and saves the previously requested route. If a new accident comes in, it will check if that accident intersects with the previously requested route, and if so it sends a new route automatically that avoids the accident. In the updated route, it adds "updated: True" field in the route object so it can be distinguished from normal route responses. The updated route is sent to the same topic as other routes.

## Running this

To run this without docker, use:

<pre>python3 -m src.main</pre>

To run this in a docker container, use:

<pre>docker-compose up</pre>

Make sure all of the environment variables are set.

### Environment variables required

<b>MQTT_URL</b>: The url where the broker is located

<b>MQTT_PORT</b>: Port to use when connecting to the broker

<b>MQTT_REQUEST_TOPIC</b>: route/requests

<b>MQTT_RESPONSE_TOPIC</b>: route/responses

<b>OPENROUTESERVICE_API_KEY</b>: API key to connect to OpenRouteService API. The key can be obtained from https://openrouteservice.org/

<b>MOCK_API_URL</b> URL for Mock API to fetch accidents from.

<b>MOCK_API_KEY</b>: API key to authenticate to Mock API.

Examples for these can be found from docker-compose file.

## MQTT topics

MQTT client subscribes to two topics: requests and responses.
It supports receiving a route with no modifications and also receiving a route that avoids a certain area.
<br>

The topics are:

<pre>route/requests</pre>
<pre>route/responses</pre>

In requests topic, it listens for route requests. In responses topic, it sends the route object in JSON format.

Request message format for receiving a route is:

<pre>{ "start": [25.466337, 65.059248], "end": [25.3523, 65.1765] }</pre>

Where longitude comes first and latitude second. The example route is from University of Oulu to Haukipudas.

Optionally, preference for the route can also be added in the request. The options are <b>fastest</b>, <b>slowest</b> and <b>recommended</b>.
This can be done by adding a "preference" field in the message.

For example:

<pre>"preference": "fastest"</pre>

### Running tests

To run all tests, install pytest and run the command

<pre>pytest</pre>

To run a specific test with stacktrace, use:

<pre>pytest -s testname.py</pre>

#### Github Actions workflow

Additionally, a basic Github Actions workflow is set, that triggers when a pull request is made to main branch and automatically executes all tests.
Running the tests requires a working OpenRouteService API key. To add the key, go to settings -> secrets and variables -> actions and click "New repository secret". Add the key with the name OPENROUTESERVICE_API_KEY.

### Testing manually through CLI:

Make sure Mosquitto is installed. It can be installed and started with:

<pre>sudo apt update -y && sudo apt install mosquitto mosquitto-clients -y
sudo systemctl start mosquitto</pre>

#### Subscribe to topics

Requests

<pre>mosquitto_sub -h asd-mqtt.rahtiapp.fi -p 443 --tls-use-os-certs -t route/requests</pre>

Responses

<pre>mosquitto_sub -h asd-mqtt.rahtiapp.fi -p 443 --tls-use-os-certs -t route/responses</pre>

#### Send route request

Default route

<pre>mosquitto_pub -h asd-mqtt.rahtiapp.fi -p 443 --tls-use-os-certs -t route/requests -m '{"start": [25.466337, 65.059248], "end": [25.3523, 65.17651]}'</pre>

Route with preference

<pre>mosquitto_pub -h asd-mqtt.rahtiapp.fi -p 443 --tls-use-os-certs -t route/requests -m '{"start": [25.466337, 65.059248], "end": [25.3523, 65.17651], "preference": "shortest"}'</pre>
