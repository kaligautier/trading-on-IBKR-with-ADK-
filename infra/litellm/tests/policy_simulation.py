"""Run real bootstrap HTTP calls against the local Postman management simulation.

Start the simulation, then run with --base-url http://127.0.0.1:4967/management/.
This verifies client behavior; native_gateway_smoke.py verifies the actual proxy.
"""

import argparse

import httpx

from test_configuration import load_script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    script = load_script("bootstrap_scanner_key")
    team = {"team_id": "agents", "team_alias": "agents", "models": ["offline-model"]}
    policy = {
        "team_id": "agents",
        "models": ["offline-model"],
        "max_budget": 3,
        "budget_duration": "1d",
    }
    with httpx.Client(
        base_url=args.base_url,
        headers={
            "Authorization": "Bearer offline-only-master",
        },
        timeout=10,
    ) as client:
        client.post("__reset").raise_for_status()
        for _ in range(2):
            script.reconcile_team(client, team)
            script.reconcile_key(client, "offline-only-agent", policy)
        state = client.get("__state").raise_for_status().json()
        assert state["team"] == team
        assert state["updates"] == 1
        assert state["info"]["spend"] == 2.5
        assert state["info"]["budget_reset_at"] == "daily-window"
        assert all(state["info"][k] == v for k, v in policy.items())
        client.post("__fail").raise_for_status()
        try:
            script.reconcile_team(client, team)
        except script.BootstrapError as error:
            assert "HTTP 503" in str(error)
            assert "PRIVATE_UPSTREAM_DETAILS" not in str(error)
        else:
            raise AssertionError("Upstream failure was ignored")
    print(
        "PASS: real HTTP team/key reconciliation, preserved spend, stable rerun and safe 503"
    )


if __name__ == "__main__":
    main()
