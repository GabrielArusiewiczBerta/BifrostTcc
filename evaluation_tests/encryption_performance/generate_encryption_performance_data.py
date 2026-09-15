from evaluation_tests.encryption_size.generate_encryption_size_data import generate_string_of_length, verify_sizes
from evaluation_tests.test_error import InputSizeError
from api import store
from blockchain import Blockchain
import time
from random import choice, randint
from string import ascii_letters, digits
import csv


def generate_passwords(n, prints=False):
    # generate a specified number of random passwords of fixed length (10 chars)
    passwords = [(''.join(choice(ascii_letters + digits) for j in range(10))) for i in range(n)]
    if prints:
        print("generated", n, "passwords:", passwords)
    return passwords


def write_to_csv(runs, base, n, multiple_string_sizes, nr_passwords, sizes, encrypted, unencrypted,
                 increase, min_enc, max_enc, min_no_enc, max_no_enc):
    # determine filename
    if multiple_string_sizes:
        filename = "multiple_string_sizes.csv"
    else:
        filename = "unknown_case.csv"

    # determine file content
    with open(filename, 'w', newline='') as csv_file:
        fieldnames = ['string_size', 'unencrypted', 'encrypted', 'increase', 'min_no_enc', 'max_no_enc', 'min_enc',
                      'max_enc', 'params']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        # params row
        params = "runs = {0}, base = {1}, n = {2}, multiple_string_sizes = {3}, nr_passwords = {4}"\
            .format(runs, base, n, multiple_string_sizes, nr_passwords)
        writer.writerow({'string_size': None, 'unencrypted': None, 'encrypted': None, 'increase': None,
                         'min_no_enc': None, 'max_no_enc': None, 'min_enc': None, 'max_enc': None, 'params': params})

        # write actual data (per string-size)
        for i in range(n):
            writer.writerow({'string_size': sizes[i],
                             'unencrypted': unencrypted[i],
                             'encrypted': encrypted[i],
                             'increase': increase[i],
                             'min_no_enc': min_no_enc[i],
                             'max_no_enc': max_no_enc[i],
                             'min_enc': min_enc[i],
                             'max_enc': max_enc[i],
                             'params': None
                             })


def write_raw_data_csv(runs, base, n, multiple_string_sizes, nr_passwords, sizes, enc, no_enc):
    filename = "raw_encryption_performance.csv"

    # determine file content
    with open(filename, 'w', newline='') as csv_file:
        fieldnames = ['string_size', 'raw_unencrypted', 'raw_encrypted', 'params']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        # params row
        params = "runs = {0}, base = {1}, n = {2}, multiple_string_sizes = {3}, nr_passwords = {4}"\
            .format(runs, base, n, multiple_string_sizes, nr_passwords)
        writer.writerow({'string_size': None, 'raw_unencrypted': None, 'raw_encrypted': None,
                         'params': params})

        # write actual data
        for i in range(n):
            # for each string size write a row for each runs * nr_passwords
            # containing the unencrypted and encrypted value
            for j in range(runs * nr_passwords):
                writer.writerow({
                    'string_size': sizes[i],
                    'raw_unencrypted': no_enc[i][j],
                    'raw_encrypted': enc[i][j],
                    'params': None
                })


def generate_encryption_performance_data(runs=30, base=2, n=13, multiple_sizes=True, nr_passwords=5, prints=False):
    # for each run, perform separate encryption procedure

    # arrays will hold for each run the time with and without encryption averaged over
    # both input sizes and passwords
    times_no_encryption = [[] for _ in range(runs)]
    times_encryption = [[] for _ in range(runs)]

    # for storing raw data per string-size (across passwords and runs)
    raw_no_enc = [[] for _ in range(n)]
    raw_enc = [[] for _ in range(n)]

    # determine needed lengths (all runs use same lengths)
    if multiple_sizes:
        lengths = [base ** i for i in range(n)]
    else:
        lengths = [32]
        n = 1
    if prints:
        print("\nusing string sizes:", lengths)

    # min and max execution times tracked per string-size
    # times_min_enc = [[0.0]*n] * runs
    times_min_enc = [[0.0]*n for _ in range(runs)]
    times_max_enc = [[0.0]*n for _ in range(runs)]
    times_min_no_enc = [[0.0]*n for _ in range(runs)]
    times_max_no_enc = [[0.0]*n for _ in range(runs)]

    for i in range(runs):
        if prints:
            print("\n\n#########################################"
                  "\n\t\tin RUN iteration:", i,
                  "\n#########################################\n")

        # generate passwords (constant for a given run)
        passwords = generate_passwords(nr_passwords, prints)

        # generate strings of needed lengths
        strings = generate_string_of_length(lengths, prints)

        # verify sizes
        verify_sizes(lengths, strings, prints)

        no_encryption = [0.0] * n
        encryption = [0.0] * n

        for j in range(n):
            # loop for each string-size. Using Ethereum, as virtually no size limit, hence
            # potential performance impact of splitting is avoided

            # reset for each string-size
            encryption_sum = 0
            no_encryption_sum = 0
            min_enc = 0
            max_enc = 0
            min_no_enc = 0
            max_no_enc = 0

            for k in range(nr_passwords):
                # time transaction creation without encryption (time in ms)
                start = int(round(time.time() * 1000))
                store(strings[j], Blockchain.ETHEREUM)
                end = int(round(time.time() * 1000))
                no_encryption_sum += end - start
                # track raw data
                raw_no_enc[j].append(end-start)
                # track min/max
                if k == 0:
                    # first iteration define min/max
                    min_no_enc = end-start
                    max_no_enc = end-start
                if (end - start) < min_no_enc:
                    min_no_enc = end - start
                if (end - start) > max_no_enc:
                    max_no_enc = end - start

                # time transaction creation for each password (time in ms)
                start = int(round(time.time() * 1000))
                store(strings[j], Blockchain.ETHEREUM, passwords[k])
                end = int(round(time.time() * 1000))
                encryption_sum += end - start
                # track raw data
                raw_enc[j].append(end-start)
                # track min/max
                if k == 0:
                    # first iteration define min/max
                    min_enc = end-start
                    max_enc = end-start
                if (end - start) < min_enc:
                    min_enc = end - start
                if (end - start) > max_enc:
                    max_enc = end - start

            # aggregate over passwords
            no_encryption[j] = no_encryption_sum / nr_passwords
            encryption[j] = encryption_sum / nr_passwords

            # store min/max
            times_min_no_enc[i][j] = min_no_enc
            times_max_no_enc[i][j] = max_no_enc
            times_min_enc[i][j] = min_enc
            times_max_enc[i][j] = max_enc

        # store per data per byte-size
        times_no_encryption[i] = no_encryption
        times_encryption[i] = encryption

    # aggregate over runs
    t_no_enc = [0] * n
    t_enc = [0] * n
    t_min_no_enc = [0.0] * n
    t_max_no_enc = [0.0] * n
    t_min_enc = [0.0] * n
    t_max_enc = [0.0] * n
    for i in range(n):
        sum_no_enc = 0.0
        sum_enc = 0.0
        min_e = 0.0
        max_e = 0.0
        min_ne = 0.0
        max_ne = 0.0

        for j in range(runs):
            sum_no_enc += times_no_encryption[j][i]
            sum_enc += times_encryption[j][i]
            if j == 0:
                min_e = times_min_enc[j][i]
                max_e = times_max_enc[j][i]
                min_ne = times_min_no_enc[j][i]
                max_ne = times_max_no_enc[j][i]
            if min_e < times_min_enc[j][i]:
                min_e = times_min_enc[j][i]
            if max_e > times_max_enc[j][i]:
                max_e = times_max_enc[j][i]
            if min_ne < times_min_no_enc[j][i]:
                min_ne = times_min_no_enc[j][i]
            if max_ne > times_max_no_enc[j][i]:
                max_ne = times_max_no_enc[j][i]

        t_no_enc[i] = int(sum_no_enc / runs)
        t_enc[i] = int(sum_enc / runs)
        t_min_enc[i] = min_e
        t_max_enc[i] = max_e
        t_min_no_enc[i] = min_ne
        t_max_no_enc[i] = max_ne

    if prints:
        print("aggregated unencrypted runtimes:", t_no_enc)
        print("aggregated encrypted runtimes:", t_enc)

    if prints:
        print("\n\nexecution times without encryption (ms):", times_no_encryption)
        print("execution times with encryption (ms):", times_encryption)
        print("min & max per size without encryption:\n\t", t_min_no_enc, "\n\t", t_max_no_enc)
        print("min & max per size with encryption:\n\t", t_min_enc, "\n\t", t_max_enc)

    # calculate percentage increase
    increase = [0]*n
    for i in range(n):
        increase[i] = int(((t_enc[i]-t_no_enc[i]) / t_no_enc[i]) * 100)

    if prints:
        print("percentage increase in runtime:", increase)

    # write to csv file to avoid reruns
    write_to_csv(runs, base, n, multiple_sizes, nr_passwords, lengths, t_enc, t_no_enc, increase,
                 t_min_enc, t_max_enc, t_min_no_enc, t_max_no_enc)

    # raw data for potential boxplot (all times per size across runs)
    write_raw_data_csv(runs, base, n, multiple_sizes, nr_passwords, lengths, raw_enc, raw_no_enc)
    if prints:
        print("raw data per string-size: \n\tno encryption:", raw_no_enc, "\n\tencryption:", raw_enc)


# TODO: for testing
# warmup_loops = 0
# for x in range(warmup_loops+1):
#     generate_encryption_performance_data(runs=1, n=3, nr_passwords=3, prints=True)

# TODO: use for actual data run. increased available ETH to 100k, so should work :))
# warmup_loops = 3
# for x in range(warmup_loops+1):
#     generate_encryption_performance_data(runs=30, n=13, nr_passwords=10, prints=True)
