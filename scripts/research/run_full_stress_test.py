#!/usr/bin/env python3
# Simple runner for full stress test
import sys
sys.path.insert(0, '.')

# Set config for full test
import test_stress_smart_answer as stress_test
stress_test.CONFIG["max_products"] = 100
stress_test.CONFIG["questions_per_product"] = 5

# Run
if __name__ == "__main__":
    print("="*80)
    print("STARTING FULL STRESS TEST: 100 products x 5 questions = 500 tests")
    print("="*80)
    stress_test.main()
