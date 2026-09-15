import csv


def extract_data_from_csv(prints=False):
    # NOTE: function specifically written for 'multiple_string_sizes.csv', not
    #  usable

    sizes = []
    encrypted = []
    unencrypted = []
    increase = []

    # extract from csv
    # https://docs.python.org/3/library/csv.html
    with open('multiple_string_sizes.csv', newline='') as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            # skip params row
            if row['params'] == '':
                sizes.append(int(row['string_size']))
                encrypted.append(int(row['encrypted']))
                unencrypted.append(int(row['unencrypted']))
                increase.append(int(row['increase']))

    if prints:
        print("sizes:", sizes)
        print("unencrypted:", unencrypted)
        print("encrypted:", encrypted)
        print("increase", increase)

    return sizes, unencrypted, encrypted, increase

