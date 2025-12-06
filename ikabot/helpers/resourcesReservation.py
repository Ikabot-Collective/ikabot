import os
import json
from ikabot.config import RESERVATION_FILE, enable_Reservation
import psutil

# Structure: {city_id: {resource: [{"pid": ..., "amount": ...}, ...]}}

def _load():
    if not os.path.exists(RESERVATION_FILE):
        return {}
    with open(RESERVATION_FILE, 'r') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def _save(data):
    with open(RESERVATION_FILE, 'w') as f:
        json.dump(data, f)

def get_reserved(city_id, resource):
    if not enable_Reservation:
        return 0
    clearReservations()
    data = _load()
    city_id = str(city_id)
    resource = str(resource)
    entries = data.get(city_id, {}).get(resource, [])
    # Ensure entries is a list to avoid iterating over an int or other types
    if not isinstance(entries, list):
        return 0
    total = 0
    for entry in entries:
        total += entry["amount"]
    return total

def reserve(city_id, resource, amount, pid):
    if not enable_Reservation:
        return
    data = _load()
    city_id = str(city_id)
    resource = str(resource)
    if city_id not in data:
        data[city_id] = {}
    if resource not in data[city_id]:
        data[city_id][resource] = []
    data[city_id][resource].append({"pid": pid, "amount": amount})
    _save(data)

def release(city_id, resource, amount, pid):
    if not enable_Reservation:
        return
    data = _load()
    city_id = str(city_id)
    resource = str(resource)
    local_amount = amount
    if city_id in data and resource in data[city_id]:
        entries = data[city_id][resource]
        for entry in entries:
            if entry["pid"] == pid:
                if entry["amount"] > local_amount:
                    entry["amount"] -= local_amount
                    local_amount = 0
                    break
                else:
                    local_amount -= entry["amount"]
                    entry["amount"] = 0
        # Remove zeroed entries
        data[city_id][resource] = [e for e in entries if e["amount"] > 0]
        if not data[city_id][resource]:
            del data[city_id][resource]
        if not data[city_id]:
            del data[city_id]
        _save(data)

def release_all_for_pid(pid):
    data = _load()
    changed = False
    for city_id in list(data.keys()):
        for resource in list(data[city_id].keys()):
            entries = data[city_id][resource]
            new_entries = [e for e in entries if e["pid"] != pid]
            if len(new_entries) != len(entries):
                data[city_id][resource] = new_entries
                changed = True
            if not data[city_id][resource]:
                del data[city_id][resource]
        if not data[city_id]:
            del data[city_id]
    if changed:
        _save(data)

def get_available(city, city_id, resource):
    real = city["availableResources"][resource]
    reserved = get_reserved(city_id, resource)
    return real - reserved

def get_all_reserved_pids():
    """Returns the set of all PIDs present in the reservation file."""
    data = _load()
    pids = set()
    for city in data.values():
        for resource in city.values():
            for entry in resource:
                pids.add(entry["pid"])
    return pids


def clearReservations():
    # Clean up reservations for inactive or non-Python PIDs
    try:
        reserved_pids = get_all_reserved_pids()
        active_python_pids = set(
            p.pid for p in psutil.process_iter(['name'])
            if p.info['name'] and 'python' in p.info['name'].lower()
        )
        for pid in reserved_pids:
            if pid not in active_python_pids:
                release_all_for_pid(pid)
    except Exception as e:
        print(f"[Warning] Unable to clean up resource reservations: {e}")
