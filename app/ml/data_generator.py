from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

# Fixed seed for perfect reproducibility
DEFAULT_RANDOM_SEED = 42

CATEGORIES = ["HVAC", "PLUMBING", "ELECTRICAL", "APPLIANCE", "ROOFING"]
URGENCIES = ["ROUTINE", "MEDIUM", "HIGH", "EMERGENCY"]
EQUIPMENT_BY_CATEGORY = {
    "HVAC": ["heat_pump", "central_ac", "gas_furnace", "mini_split", "thermostat"],
    "PLUMBING": ["water_heater", "main_drain", "sump_pump", "pipe_manifold", "faucet_toilet"],
    "ELECTRICAL": ["main_breaker_panel", "subpanel", "ev_charger", "wiring_circuit", "generator"],
    "APPLIANCE": ["refrigerator", "dishwasher", "washing_machine", "dryer", "oven_range"],
    "ROOFING": ["asphalt_shingles", "metal_roof", "tile_roof", "gutters_downspout", "flashing"],
}

CATEGORY_BASE_DURATION = {
    "HVAC": 80.0,
    "PLUMBING": 65.0,
    "ELECTRICAL": 55.0,
    "APPLIANCE": 45.0,
    "ROOFING": 120.0,
}


def generate_synthetic_field_service_dataset(
    n_samples: int = 2500,
    seed: int = DEFAULT_RANDOM_SEED,
    start_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Generates a realistic, chronological synthetic field service dataset.

    Documented Assumptions:
    1. Base duration varies by trade category (Roofing > HVAC > Plumbing > Electrical > Appliance).
    2. Experienced technicians (> 6 years) work ~15% faster; older equipment (> 10 yrs) adds ~20% duration.
    3. Fatigue/workload: technicians with >= 3 prior jobs in a day experience small slowdowns (+10%).
    4. Missed/Late Appointment target (is_missed_or_late):
       - Baseline rate is ~12-14%.
       - Customer no-show history is the strongest predictor (adds +35% risk).
       - High lead time (> 7 days) increases forgetfulness/cancellation (+15% risk).
       - Long travel distance (> 25 km) combined with afternoon rush hour increases late arrival (+20% risk).
    5. Missingness: Equipment age is missing ~20% of the time; equipment type missing ~10%.
    """
    rng = np.random.default_rng(seed)
    start_dt = start_date or datetime(2026, 1, 1, 8, 0, tzinfo=UTC)

    records: list[dict[str, Any]] = []

    for i in range(n_samples):
        # Timestamp spaced over a 180-day chronological timeline
        offset_minutes = int(rng.uniform(0, 180 * 24 * 60))
        appt_dt = start_dt + timedelta(minutes=offset_minutes)

        category = rng.choice(CATEGORIES, p=[0.30, 0.25, 0.20, 0.15, 0.10])
        urgency = rng.choice(URGENCIES, p=[0.20, 0.45, 0.25, 0.10])

        # Equipment
        eq_list = EQUIPMENT_BY_CATEGORY[category]
        equipment_type = rng.choice(eq_list)
        # 10% missing equipment type
        if rng.random() < 0.10:
            equipment_type = None

        # Equipment age (years)
        equipment_age = float(np.clip(rng.gamma(shape=2.5, scale=3.0), 0.5, 30.0))
        # 20% missing equipment age
        if rng.random() < 0.20:
            equipment_age = None

        # Technician attributes
        tech_exp = float(np.clip(rng.normal(loc=5.5, scale=3.0), 0.5, 25.0))
        if rng.random() < 0.05:
            tech_exp = None

        tech_active_jobs = int(rng.choice([0, 1, 2, 3, 4], p=[0.15, 0.35, 0.30, 0.15, 0.05]))
        travel_distance_km = float(np.clip(rng.exponential(scale=12.0), 1.0, 60.0))

        # Customer attributes
        cust_total_jobs = int(rng.geometric(p=0.4))
        # Customer no-show history: most have 0, small fraction have 1 or 2
        cust_no_shows = int(rng.choice([0, 1, 2], p=[0.85, 0.12, 0.03]))

        # Lead time between booking and appointment (hours)
        lead_time_hours = float(np.clip(rng.exponential(scale=48.0), 1.0, 336.0))

        # Schedule properties
        hour_of_day = appt_dt.hour
        day_of_week = appt_dt.weekday()

        # -------------------------------------------------------------
        # Target A: Actual Job Duration (Minutes)
        # -------------------------------------------------------------
        base_dur = CATEGORY_BASE_DURATION[category]
        dur = base_dur

        # Urgency impact
        if urgency == "EMERGENCY":
            dur += rng.normal(15.0, 4.0)
        elif urgency == "HIGH":
            dur += rng.normal(8.0, 3.0)

        # Equipment age impact
        if equipment_age is not None and equipment_age > 10.0:
            dur += (equipment_age - 10.0) * 1.8

        # Technician experience impact (efficiency gain)
        eff_exp = tech_exp if tech_exp is not None else 5.0
        dur *= max(0.80, 1.15 - (eff_exp * 0.025))

        # Workload / fatigue
        if tech_active_jobs >= 3:
            dur *= 1.10

        # Travel distance minor effect on setup
        dur += travel_distance_km * 0.15

        # Stochastic noise
        dur += rng.normal(0.0, 8.0)
        actual_duration_minutes = float(np.clip(dur, 20.0, 360.0))

        # -------------------------------------------------------------
        # Target B: Missed-Appointment / Late Arrival Risk (Binary)
        # Definition: Customer no-show, cancellation < 2h prior, or tech arrival > 30 min late
        # -------------------------------------------------------------
        risk_logit = -2.2  # Baseline log-odds (~10% base probability)

        if cust_no_shows > 0:
            risk_logit += 1.3 * cust_no_shows  # Strong historical signal

        if lead_time_hours > 120.0:
            risk_logit += 0.6  # High lead time -> forgotten appointment

        # Rush hour (16:00 - 18:00) with long travel distance
        if (16 <= hour_of_day <= 18) and travel_distance_km > 20.0:
            risk_logit += 0.9

        # Inexperienced tech + high active jobs
        if eff_exp < 2.0 and tech_active_jobs >= 3:
            risk_logit += 0.5

        if urgency == "EMERGENCY":
            risk_logit -= 0.8  # Emergencies are rarely missed by customer

        risk_prob = 1.0 / (1.0 + np.exp(-risk_logit))
        is_missed_or_late = int(rng.random() < risk_prob)

        records.append(
            {
                "appointment_id": f"APPT-SYNTH-{10000 + i}",
                "timestamp": appt_dt.isoformat(),
                "category": category,
                "urgency": urgency,
                "equipment_type": equipment_type,
                "equipment_age_years": equipment_age,
                "technician_experience_years": tech_exp,
                "technician_active_jobs_count": tech_active_jobs,
                "historical_jobs_completed": cust_total_jobs,
                "customer_total_jobs": cust_total_jobs,
                "customer_no_show_history_count": cust_no_shows,
                "travel_distance_km": travel_distance_km,
                "distance_km": travel_distance_km,
                "lead_time_hours": lead_time_hours,
                "scheduled_hour_of_day": hour_of_day,
                "scheduled_day_of_week": day_of_week,
                "estimated_duration_minutes": float(CATEGORY_BASE_DURATION[category]),
                # Ground truth targets
                "actual_duration_minutes": round(actual_duration_minutes, 1),
                "is_missed_or_late": is_missed_or_late,
            }
        )

    # Sort strictly chronologically to guarantee temporal split validity
    records.sort(key=lambda r: r["timestamp"])
    return records


def split_dataset_temporally(
    data: list[dict[str, Any]],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Splits chronological dataset into train, validation, and test partitions
    WITHOUT data leakage across future timestamps.
    """
    n = len(data)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_data = data[:train_end]
    val_data = data[train_end:val_end]
    test_data = data[val_end:]

    return train_data, val_data, test_data


def generate_synthetic_dataset(
    num_samples: int = 2500,
    seed: int = DEFAULT_RANDOM_SEED,
    start_date: datetime | None = None,
) -> list[dict[str, Any]]:
    return generate_synthetic_field_service_dataset(
        n_samples=num_samples, seed=seed, start_date=start_date
    )
