import azure.functions as func
import logging
import json
import os
import requests
import time
from azure.core.messaging import CloudEvent

app = func.FunctionApp()

def get_logger():
    return logging.getLogger(__name__)

def get_simulation_id():
    simulation_id = os.environ.get('SimulationId')
    if not simulation_id:
        raise ValueError("SimulationId cannot be null")
    return simulation_id

def get_simulation_schema():
    simulation_schema = os.environ.get('SimulationSchema')
    if not simulation_schema:
        raise ValueError("SimulationSchema cannot be null")
    return simulation_schema

def get_simulator_base_url():
    simulator_base_url = os.environ.get('SimulatorUrlPrefix')
    if not simulator_base_url:
        raise ValueError("SimulatorUrlPrefix cannot be null")
    return simulator_base_url

async def process_simulation_event(cloud_event):
    logger = get_logger()
    logger.info(f"Event type: {cloud_event.type}, Event subject: {cloud_event.subject}")
    
    simulation_id = get_simulation_id()
    simulation_schema = get_simulation_schema()
    
    if not cloud_event.data:
        raise ValueError("Event data cannot be null")
    
    # Transform event data
    input_data = transform_event_data(cloud_event.data, simulation_schema)
    
    # Input simulation data
    await input_simulation_data(simulation_id, input_data)
    
    # Resume simulation
    await resume_simulation(simulation_id)
    
    # Check simulation status
    while True:
        status = await get_simulation_status(simulation_id)
        logger.info(f"Simulation status: {status}")
        if status == "IDLE":
            break
        time.sleep(1)
    
    # Get results
    return await get_simulation_results(simulation_id)

@app.event_grid_trigger(arg_name="event")
@app.event_hub_output(arg_name="$return", 
                     event_hub_name="digital-twin", 
                     connection="EventHubConnectionString")
async def simulation_loop_event_grid(event: func.EventGridEvent) -> str:
    try:
        return await process_simulation_event(CloudEvent.from_json(event.get_json()))
    except Exception as ex:
        get_logger().error(f"Error processing Event Grid request: {str(ex)}")
        return ""

@app.route(route="webhook", methods=["POST", "OPTIONS"])
async def simulation_loop_webhook(req: func.HttpRequest) -> func.HttpResponse:
    if req.method.upper() == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "WebHook-Allowed-Origin": "*",
                "WebHook-Allowed-Rate": "*"
            }
        )
    
    try:
        body = req.get_body().decode()
        if not body:
            return func.HttpResponse(
                json.dumps({"message": "Request body is empty"}),
                status_code=400,
                mimetype="application/json"
            )
        
        cloud_event = CloudEvent.from_json(body)
        results = await process_simulation_event(cloud_event)
        
        return func.HttpResponse(
            results,
            status_code=200,
            mimetype="application/json"
        )
    except Exception as ex:
        return func.HttpResponse(
            json.dumps({"message": f"Error processing request: {str(ex)}"}), 
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="start", methods=["PUT"])
async def start_simulation(req: func.HttpRequest) -> func.HttpResponse:
    logger = get_logger()
    logger.info("Processing Start Simulation request")
    
    try:
        simulation_id = get_simulation_id()
        simulation_initiated = await initiate_simulation(simulation_id)
        
        if not simulation_initiated:
            return func.HttpResponse(
                json.dumps({"error": "Failed to initiate simulation"}),
                status_code=500,
                mimetype="application/json"
            )
        
        return func.HttpResponse(
            json.dumps({"result": simulation_initiated}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as ex:
        logger.error(f"Error starting simulation: {str(ex)}")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="stop", methods=["PUT"])
async def stop_simulation(req: func.HttpRequest) -> func.HttpResponse:
    logger = get_logger()
    logger.info("Processing Stop Simulation request")
    
    try:
        simulation_id = get_simulation_id()
        simulation_stopped = await stop_simulation(simulation_id)
        
        if not simulation_stopped:
            return func.HttpResponse(
                json.dumps({"error": "Failed to stop simulation"}),
                status_code=500,
                mimetype="application/json"
            )
        
        return func.HttpResponse(
            json.dumps({"result": simulation_stopped}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as ex:
        logger.error(f"Error stopping simulation: {str(ex)}")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json"
        )

# Helper functions

def transform_event_data(event_data, simulation_schema):
    # Placeholder for actual transformation logic
    return event_data

async def initiate_simulation(simulation_id):
    response = requests.put(f"{get_simulator_base_url()}/simulations/{simulation_id}/start")
    response.raise_for_status()
    get_logger().info(f"/start response: {response.text}")
    return response.json()["result"]

async def input_simulation_data(simulation_id, input_data):
    response = requests.put(
        f"{get_simulator_base_url()}/simulations/{simulation_id}/input/data",
        json=input_data,
        headers={"Content-Type": "application/json"}
    )
    response.raise_for_status()
    get_logger().info(f"/input/data response: {response.text}")

async def resume_simulation(simulation_id):
    response = requests.put(f"{get_simulator_base_url()}/simulations/{simulation_id}/resume")
    response.raise_for_status()
    get_logger().info(f"/resume response: {response.text}")
    return response.text

async def get_simulation_status(simulation_id):
    response = requests.get(f"{get_simulator_base_url()}/simulations/{simulation_id}/status")
    response.raise_for_status()
    get_logger().info(f"/status response: {response.text}")
    return response.json()["status"]

async def get_simulation_results(simulation_id):
    response = requests.get(f"{get_simulator_base_url()}/simulations/{simulation_id}/results")
    response.raise_for_status()
    get_logger().info(f"/results response: {response.text}")
    return response.text

async def stop_simulation(simulation_id):
    response = requests.put(f"{get_simulator_base_url()}/simulations/{simulation_id}/stop")
    response.raise_for_status()
    get_logger().info(f"/stop response: {response.text}")
    return response.json()["result"]