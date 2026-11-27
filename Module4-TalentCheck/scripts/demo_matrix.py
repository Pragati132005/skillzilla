"""Prints readiness for the 4 sample candidates against the companies used in the hackathon JD pack."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.helpers import load_samples, make_service  # noqa: E402

svc = make_service()
companies = ["Google LLC", "Microsoft Corporation", "Oracle Financial Services", "Infosys"]
samples = load_samples()
print(f"{'':10}" + "".join(f"{c.split()[0]:>12}" for c in companies))
for name, p in samples.items():
    print(f"{name:10}" + "".join(f"{svc.run(p, c)['readiness_score']:>12}" for c in companies))
print()
r0 = svc.run(samples["Ananya"], "Google LLC")
print("Ananya vs Google  (level/required):", " ".join(
    f"{g['category_code']} {g['candidate_level']}/{g['required_level']}" for g in r0["skillset_gap"]))
