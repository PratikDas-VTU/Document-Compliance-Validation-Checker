import os
import json
import datetime
from app.utils.path_helper import get_data_dir

def log_activity(message: str, event_type: str, document_name: str = "") -> None:
    """Logs an activity event persistently to activity_log.json."""
    act_path = os.path.join(get_data_dir(), "activity_log.json")
    activity_log = []
    if os.path.exists(act_path):
        try:
            with open(act_path, "r", encoding="utf-8") as f:
                activity_log = json.load(f)
        except Exception:
            activity_log = []
            
    # Insert new event at the beginning
    activity_log.insert(0, {
        "message": message,
        "activity_type": event_type,
        "document": document_name,
        "timestamp": datetime.datetime.now().isoformat()
    })
    
    # Cap at 50 entries
    activity_log = activity_log[:50]
    
    try:
        with open(act_path, "w", encoding="utf-8") as f:
            json.dump(activity_log, f, indent=2)
    except Exception:
        pass


def get_learning_stats() -> dict:
    """Returns the persistent learning statistics (approved and rejected count)."""
    stats_path = os.path.join(get_data_dir(), "learning_stats.json")
    fallback = {"approved_count": 0, "rejected_count": 0}
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback
    return fallback


def increment_learning_stat(stat_type: str) -> None:
    """Increments either approved_count or rejected_count persistently."""
    stats = get_learning_stats()
    key = f"{stat_type}_count"
    stats[key] = stats.get(key, 0) + 1
    
    stats_path = os.path.join(get_data_dir(), "learning_stats.json")
    try:
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def get_discovery_stats() -> dict:
    """Returns the persistent discovery statistics."""
    stats_path = os.path.join(get_data_dir(), "discovery_stats.json")
    fallback = {"total_discovered": 0, "total_filtered": 0, "total_eligible": 0}
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback
    return fallback


def update_discovery_stats(discovered: int, filtered: int, eligible: int) -> None:
    """Adds new candidate counts to the cumulative discovery stats."""
    stats = get_discovery_stats()
    stats["total_discovered"] = stats.get("total_discovered", 0) + discovered
    stats["total_filtered"] = stats.get("total_filtered", 0) + filtered
    stats["total_eligible"] = stats.get("total_eligible", 0) + eligible
    
    stats_path = os.path.join(get_data_dir(), "discovery_stats.json")
    try:
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass
