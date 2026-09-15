from random import choice, randint
from string import ascii_letters, digits
from adapters.adapter import Adapter
from evaluation_tests.encryption_size.generate_encryption_size_data import generate_string_of_length
import time
from statistics import pstdev
import csv


def generate_passwords(n, l, l_upper=None, prints=False):
    # generate a specified number of random passwords of either fixed lenght (l) or random length (l to l_upper)
    if l_upper is None:
        l_upper = l

    passwords = [(''.join(choice(ascii_letters + digits) for j in range(int(randint(l, l_upper))))) for i in range(n)]
    if prints:
        print("generated", n, "passwords:", passwords)
    return passwords


def write_to_csv(n, l, l_upper, runs, new_strings, base, exp, sizes, times, prints=False):
    # determine case for file-name
    if n == 1 and l_upper is None and not new_strings:
        # fixed fixed len pw, fixed strings
        filename = "single_fixed_len_pw.csv"
    elif n != 1 and l_upper is None and not new_strings:
        # random fixed len pws, fixed strings
        filename = "random_fixed_len_pws.csv"
    elif n != 1 and l_upper is not None and not new_strings:
        # random random len pws, fixed strings
        filename = "random_random_len_pws.csv"
    elif n == 1 and l_upper is None and new_strings:
        # fixed fixed len pw, random fixed len strings (new strings for each run)
        filename = "single_fixed_len_pw_new_strings.csv"
    else:
        filename = "unknown_case.csv"

    # determine file content
    # https://docs.python.org/3/library/csv.html
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['string_size', 'avg', 'max', 'min', 'sd', 'params']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        # write row with params
        params = "n = {0}, l = {1}, l_upper = {2}, runs = {3}, new_strings = {4}, base = {5}, exp = {6}"\
            .format(n, l, l_upper, runs, new_strings, base, exp)
        writer.writerow({'string_size': None, 'avg': None, 'max': None, 'min': None, 'sd': None, 'params': params})

        # write time data
        for i in range(exp):
            writer.writerow({'string_size': sizes[i],
                             'avg': times[i][0],
                             'max': times[i][1],
                             'min': times[i][2],
                             'sd': times[i][3],
                             'params': None
                             })


def write_raw_to_csv(n, l, l_upper, runs, new_strings, base, exp, sizes, raw):
    # determine case for file-name
    if n == 1 and l_upper is None and not new_strings:
        # fixed fixed len pw, fixed strings
        filename = "single_fixed_len_pw_RAW.csv"
    elif n != 1 and l_upper is None and not new_strings:
        # random fixed len pws, fixed strings
        filename = "random_fixed_len_pws_RAW.csv"
    elif n != 1 and l_upper is not None and not new_strings:
        # random random len pws, fixed strings
        filename = "random_random_len_pws_RAW.csv"
    elif n == 1 and l_upper is None and new_strings:
        # fixed fixed len pw, random fixed len strings (new strings for each run)
        filename = "single_fixed_len_pw_new_strings_RAW.csv"
    else:
        filename = "unknown_case_RAW.csv"

    # determine file content
    with open(filename, 'w', newline='') as csv_file:
        fieldnames = ['string_size', 'raw(ms)', 'params']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        # write row with params
        params = "n = {0}, l = {1}, l_upper = {2}, runs = {3}, new_strings = {4}, base = {5}, exp = {6}" \
            .format(n, l, l_upper, runs, new_strings, base, exp)
        writer.writerow({'string_size': None, 'raw(ms)': None, 'params': params})

        # write time data
        for i in range(exp):
            # for each string-size write a column for each runs * n (n = #passwords)
            for j in range(n * runs):
                writer.writerow({
                    'string_size': sizes[i],
                    'raw(ms)': raw[i][j],
                    'params': None
                })


def performance_pw(n, l, l_upper=None, runs=10, new_strings=False, base=2, exp=13, prints=False):
    # evaluate performance of fixed length passwords for fixed strings of different predefined lengths
    string_sizes = [base ** i for i in range(exp)]
    if prints:
        print("\nworking with string sizes:", string_sizes)

    # for raw times per string-size
    raw_times = [[] for _ in range(exp)]


    # generate a fixed set of strings to be evaluated for each password
    strings = []
    if not new_strings:
        strings = generate_string_of_length(string_sizes, prints)

    # generate passwords
    if l_upper is None:
        passwords = generate_passwords(n, l, prints=prints)
    else:
        passwords = generate_passwords(n, l, l_upper, prints)

    # for each string-size evaluate the average password's performance
    times = [[] for _ in range(exp)]
    for i in range(exp):
        t_arr = []
        t_min = 0
        t_max = 0

        # for each password
        for j in range(n):

            # perform k runs
            for k in range(runs):

                # generate strings per run if option set
                # NOTE: inefficient to do there, but i don't want to restructure the function :))
                if new_strings:
                    strings = generate_string_of_length(string_sizes, prints)

                start = int(round(time.time() * 1000))
                Adapter.encrypt(strings[i], passwords[j])
                end = int(round(time.time() * 1000))
                t = end - start

                raw_times[i].append(t)

                t_arr.append(t)
                if j == 0:
                    t_min = t
                if t <= t_min:
                    t_min = t
                if t >= t_max:
                    t_max = t

        # store stats per string-size
        times[i] = [sum(t_arr) / (n*runs), t_max, t_min, pstdev(t_arr)]

    if prints:
        print("aggregated data:", times)
        print("raw time data:", raw_times)

    # write to csv to avoid re-runs
    write_to_csv(n, l, l_upper, runs, new_strings, base, exp, string_sizes, times, prints)
    write_raw_to_csv(n, l, l_upper, runs, new_strings, base, exp, string_sizes, raw_times)


# generate_passwords(10, 4, 12, prints=True)
# generate_passwords(10, 4, prints=True)

performance_pw(n=1, l=10, runs=3, exp=3, prints=True)  # fixed random fixed len pw #NOTE for testing

# warmup_loops = 3
# for x in range(warmup_loops + 1):
#     # NOTE: run in loop to "warm up". comparatively high standard deviation for the fixed random fixed len pw, which
#     #  at least to me does not make sense
#     performance_pw(n=1, l=10, runs=30, exp=13, prints=True)  # fixed random fixed len pw
#     performance_pw(n=10, l=10, runs=30, exp=13, prints=True)  # 10 random fixed len pw
#     performance_pw(n=10, l=4, l_upper=20, runs=30, exp=13,  prints=True)  # 10 random random len pw
#     performance_pw(n=1, l=10, runs=30, new_strings=True, exp=13, prints=True)
#     # fixed random fixed len pw, new strings each run
