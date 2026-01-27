from app.main import app
import sys

try:
    print("Verifying Payroll Router Registration...")
    routes = [route.path for route in app.routes]
    payroll_routes = [r for r in routes if "/api/payroll" in r]
    
    if len(payroll_routes) > 0:
        print("Success: Payroll routes found:")
        for r in payroll_routes:
            print(f" - {r}")
    else:
        print("Error: No payroll routes found in app.routes")
        sys.exit(1)

    print("\nVerifying Services and Models Import...")
    from app.models.payroll import Payroll
    from app.services.payroll_ai import PayrollAIService
    print("Success: Models and Services imported correctly.")

except Exception as e:
    print(f"Verification failed: {e}")
    sys.exit(1)
