import subprocess

def run_systemctl(action, service) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["systemctl", action, service],
            capture_output=True, text=True
        )
        ok = completed.returncode == 0
        output = completed.stdout.strip() if ok else completed.stderr.strip()
        return ok, output or "Pas de sortie"
    except Exception as e:
        return False, str(e)
