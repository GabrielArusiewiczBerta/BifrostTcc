from evaluation_tests.encryption_performance.generate_encryption_performance_data import generate_encryption_performance_data
from evaluation_tests.encryption_password_performance.encryption_password_performance import performance_pw

# NOTE: comparatively short processes get 2 warmup loops, the others get 1
#   (probably still overkill)
warmup_loops = 2
for i in range(warmup_loops + 1):
    performance_pw(n=1, l=10, runs=30, exp=13, prints=True)  # fixed random fixed len pw
for i in range(warmup_loops + 1):
    performance_pw(n=1, l=10, runs=30, new_strings=True, exp=13, prints=True)
    # fixed random fixed len pw, new strings each run

warmup_loops = 1
for i in range(warmup_loops + 1):
    performance_pw(n=10, l=10, runs=30, exp=13, prints=True)  # 10 random fixed len pw
for i in range(warmup_loops + 1):
    performance_pw(n=10, l=4, l_upper=20, runs=30, exp=13, prints=True)  # 10 random random len pw
for i in range(warmup_loops + 1):
    generate_encryption_performance_data(runs=30, n=13, nr_passwords=10, prints=True)

exit(0)
