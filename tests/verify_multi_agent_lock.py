import multiprocessing
import os
import time

from dimcause.utils.state import resolve_session_path


def create_session(agent_id):
    # Set agent id env var (though resolve_session_path doesn't check it yet for path resolution,
    # it matters for future steps. Here we test the lock).
    os.environ["DIMC_AGENT_ID"] = f"agent_{agent_id}"

    # Simulate a bit of random work before requesting
    time.sleep(0.1 * (agent_id % 3))

    try:
        path, seq = resolve_session_path("start")
        return (agent_id, str(path), seq)
    except Exception as e:
        return (agent_id, "ERROR", str(e))


def verify_locking():
    # Number of concurrent agents
    num_agents = 10

    with multiprocessing.Pool(processes=num_agents) as pool:
        results = pool.map(create_session, range(num_agents))

    print("Results:")
    paths = []
    seqs = []
    errors = []

    for agent_id, path, seq in results:
        print(f"Agent {agent_id}: {path} (Seq: {seq})")
        if path == "ERROR":
            errors.append((agent_id, seq))
        else:
            paths.append(path)
            seqs.append(seq)

    # Verification
    if len(set(paths)) == len(paths):
        print("\nSUCCESS: All paths are unique.")
    else:
        print("\nFAILURE: duplicate paths found!")
        from collections import Counter

        print(Counter(paths))

    if len(set(seqs)) == len(seqs):
        print("SUCCESS: All sequence numbers are unique.")
    else:
        print("FAILURE: duplicate sequence numbers found!")

    if errors:
        print(f"Errors occurred: {errors}")


if __name__ == "__main__":
    verify_locking()
