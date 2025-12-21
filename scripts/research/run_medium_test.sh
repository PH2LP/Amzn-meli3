#!/bin/bash
python3 -u -c "
import sys
sys.path.insert(0, '.')
import test_stress_smart_answer as stress
stress.CONFIG['max_products'] = 20
stress.CONFIG['questions_per_product'] = 3
print('Starting medium stress test: 20 products × 3 questions = 60 tests')
print('='*80)
stress.main()
" 2>&1
