import matplotlib.pyplot as plt
import csv
import numpy as np


def import_data(prints=False):
    # boxplot built with raw data
    _sizes = []
    _encrypted = []
    _unencrypted = []

    # extract from csv
    with open('raw_encryption_performance.csv', newline='') as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            # skip params row
            if row['params'] == '':
                _sizes.append(int(row['string_size']))
                _unencrypted.append(int(row['raw_unencrypted']))
                _encrypted.append(int(row['raw_encrypted']))

    # condense sizes into unique entries
    # https://stackoverflow.com/a/37163210
    lengths = list(dict.fromkeys(_sizes))

    # reorganize data into per-size lists
    n = len(lengths)
    m = len(_sizes)
    enc = [[] for _ in range(n)]
    no_enc = [[] for _ in range(n)]
    for i in range(n):
        for j in range(m):
            # m => amount of actual rows in dataset
            if _sizes[j] == lengths[i]:
                no_enc[i].append(_unencrypted[j])
                enc[i].append(_encrypted[j])

    if prints:
        print("extracted values:")
        print("\tstring sizes:", lengths)
        print("unencrypted:", no_enc)
        print("encrypted:", enc)
        print("\n######### ECTRACTION DONE #########\n\n")

    return lengths, no_enc, enc


def aio_boxplot(show_outliers=True, prints=False):
    # plot includes both encrypted and unencrypted
    sizes, unencrypted, encrypted = import_data(prints)
    sizes.insert(0, '')
    plt.rcParams.update({'font.size': 16})
    labels = sizes

    x = np.arange(len(labels))

    fig, ax = plt.subplots()

    medianprops = dict(linewidth=1, color='black')
    # "unencrypted" box
    bp1 = ax.boxplot(unencrypted, patch_artist=True,
                     showfliers=show_outliers, medianprops=medianprops,
                     boxprops=dict(facecolor="xkcd:light grey"))

    # "encrypted" box
    bp2 = ax.boxplot(encrypted, patch_artist=True,
                     showfliers=show_outliers, medianprops=medianprops,
                     boxprops=dict(facecolor="xkcd:grey"))

    # axis labels and ticks
    ax.set_ylabel('Runtime [ms]')
    ax.set_xlabel('Input Size [Bytes]')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend([bp1["boxes"][0], bp2["boxes"][0]], ['Unencrypted', 'Encrypted'],
              loc='upper left')
    ax.set_axisbelow(True)

    # medians_unencrypted = [np.median(unencrypted[i]) for i in range(len(sizes) - 1)]
    # medians_encrypted = [np.median(encrypted[i]) for i in range(len(sizes) - 1)]

    plt.style.use('grayscale')
    ax.grid(True)
    fig.set_figheight(8)
    fig.set_figwidth(12)
    fig.tight_layout()
    plt.savefig('AIO_encryption_performance_box.pdf', format='pdf')

    plt.show()


def single_boxplot(is_encryption=True, prints=False):
    # extract data from csv
    sizes, unencrypted, encrypted = import_data(prints)
    sizes.insert(0, '')
    plt.rcParams.update({'font.size': 20})
    labels = sizes

    # produces boxplot of either encrypted or unencrypted
    if is_encryption:
        fig_name = 'encryption_performance_box.pdf'
        legend_labels = ['Encrypted']
        data_to_use = encrypted
    else:
        fig_name = 'unencrypted_performance_box.pdf'
        legend_labels = ['Unencrypted']
        data_to_use = unencrypted

    x = np.arange(len(labels))

    fig, ax = plt.subplots()

    medianprops = dict(linewidth=2, color='black')
    # box
    bp = ax.boxplot(data_to_use, patch_artist=True,
                    showfliers=False, medianprops=medianprops,
                    boxprops=dict(facecolor="xkcd:light blue"))

    # axis labels and ticks
    ax.set_ylabel('Runtime [ms]')
    ax.set_xlabel('Input Size [Bytes]')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend([bp["boxes"][0]], legend_labels,
              loc='upper left')
    ax.set_axisbelow(True)

    # plt.style.use('grayscale')
    ax.grid(color='xkcd:light grey')
    fig.set_figheight(8)
    fig.set_figwidth(12)
    plt.gcf().set_facecolor('white')
    fig.tight_layout()
    plt.savefig(fig_name, format='pdf')

    plt.show()


aio_boxplot(show_outliers=False)
single_boxplot(is_encryption=False)
single_boxplot(is_encryption=True)

exit(0)
