import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
from fastapi.testclient import TestClient
from app.main import app

test_client = TestClient(app)

population_request_data = {
    "n": 1000,
    "n_archetypes": 5,
    "seed": 42
}
print("Generating population...", flush=True)
population_response = test_client.post("/population/generate", json=population_request_data)
population_data = population_response.json()
print("Generated Population:", population_data, flush=True)

population_run_id = population_data["run_id"]

archetypes_response = test_client.get(f"/population/{population_run_id}/archetypes")
print(f"Retrieved {len(archetypes_response.json())} archetypes.", flush=True)

simulation_request_data = {
    "stimulus_description": "UPI digital micro-savings app starting at 10 rupees for tier-2/3 Indian consumers",
    "population_run_id": population_run_id,
    "n_archetypes_override": 2
}
print("Starting simulation with 2 archetypes...", flush=True)
simulation_response = test_client.post("/simulations/run", json=simulation_request_data)
simulation_run_id = simulation_response.json()["run_id"]
print("Simulation completed in background task for run:", simulation_run_id, flush=True)

results_response = test_client.get(f"/simulations/{simulation_run_id}/results")
results_data = results_response.json()
print("\n=== SIMULATION RESULTS ===", flush=True)
print("Status:", results_data["status"], flush=True)
if results_data.get("results"):
    print("Population Purchase Intent (0-10):", results_data["results"]["population_purchase_intent"], flush=True)
    print("Sentiment Distribution:", results_data["results"]["sentiment_distribution"], flush=True)
    print("\nArchetype Quotes:", flush=True)
    for detail in results_data["results"]["archetype_details"]:
        print(f"- Intent: {detail['purchase_intent']}/10 | Sentiment: {detail['sentiment']}", flush=True)
        print(f"  Quote: \"{detail['quote']}\"", flush=True)
        print(f"  Objection: {detail['objection']}\n", flush=True)
