import sys
import subprocess
import os

print("=== VERIFICANDO FERRAMENTAS OSINT ===")
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
print()

tools = [
    ("Sherlock", ["python", "-m", "sherlock_project", "--version"]),
    ("Maigret", ["python", "-m", "maigret", "--version"]),
    ("Holehe", ["python", "-m", "holehe", "--version"]),
]

for name, cmd in tools:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ {name}: OK - {result.stdout.strip()}")
        else:
            print(f"❌ {name}: ERRO - {result.stderr}")
    except Exception as e:
        print(f"❌ {name}: EXCEÇÃO - {e}")

print("\n=== TESTANDO FUNCIONALIDADE ===")
# Teste rápido de busca
test_cmd = ["python", "-m", "sherlock", "testuser12345", "--timeout", "2", "--print-found"]
try:
    result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
    print(f"Sherlock test output: {result.stdout[:200]}...")
except Exception as e:
    print(f"Teste falhou: {e}")