"""
Export measurement data to CSV or JSON files.
"""
import csv
import json


def export_measurements(measurements, file_path: str, log=None):
    """
    Export a list of Measurement objects to *file_path*.

    Format is determined by the file extension (.csv or .json).
    Returns True on success.
    """
    _log = log or (lambda msg, lvl="INFO": print(f"[{lvl}] {msg}"))

    try:
        if file_path.endswith('.csv'):
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'id', 'angle', 'permittivity', 'permeability',
                    'transmitted_power', 'reflected_power',
                    'transmitted_phase', 'reflected_phase', 'timestamp'
                ])
                for m in measurements:
                    writer.writerow([
                        m.id, m.angle, m.permittivity, m.permeability,
                        m.transmitted_power, m.reflected_power,
                        m.transmitted_phase, m.reflected_phase,
                        m.timestamp.isoformat()
                    ])
        else:
            data = [
                {
                    "id": m.id,
                    "angle": m.angle,
                    "permittivity": m.permittivity,
                    "permeability": m.permeability,
                    "transmitted_power": m.transmitted_power,
                    "reflected_power": m.reflected_power,
                    "transmitted_phase": m.transmitted_phase,
                    "reflected_phase": m.reflected_phase,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in measurements
            ]
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)

        _log(f"Exported {len(measurements)} records to {file_path}", "SUCCESS")
        return True
    except Exception as e:
        _log(f"Export failed: {e}", "ERROR")
        return False
