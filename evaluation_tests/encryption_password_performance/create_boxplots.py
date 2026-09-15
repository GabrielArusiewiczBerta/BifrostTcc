import matplotlib.pyplot as plt
import csv
import numpy as np
import math
import copy


def import_data(filename, prints=False):
    # boxplot is built with raw data
    _sizes = []
    _encrypted = []

    # extract from csv
    with open(filename, newline='') as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            # skip params row
            if row['params'] == '':
                _sizes.append(int(row['string_size']))
                _encrypted.append(int(row['raw(ms)']))

    # condense sizes into unique entries
    lengths = list(dict.fromkeys(_sizes))

    # reorganize data in to lists per string-size
    n = len(lengths)
    m = len(_sizes)
    enc = [[] for _ in range(n)]
    for i in range(n):
        for j in range(m):
            # m => number of rows in dataset (- params row & header)
            if _sizes[j] == lengths[i]:
                enc[i].append(_encrypted[j])

    if prints:
        print("extracted values:")
        print("\tstring sizes:", lengths)
        print("encrypted performance:\n\t", enc)

    return lengths, enc


def my_floor(x, base):
    return base * math.floor(x / base)


def my_ceil(x, base):
    return base * math.ceil(x / base)


def determine_y_axis_range(round_val=10, prints=False):
    # manually add additional files that need to be respected here
    filenames = [
        'random_fixed_len_pws_RAW.csv',
        'random_random_len_pws_RAW.csv',
        'single_fixed_len_pw_RAW.csv',
        'single_fixed_len_pw_new_strings_RAW.csv'
    ]
    v_min = 0
    v_max = 0
    for fn in filenames:
        s, e = import_data(fn)
        if prints:
            print("sizes in filename", fn, ":", s)

        for i in range(len(s)):
            if prints:
                print("data in iteration", i, " :", e[i])
            if v_min == 0 and v_max == 0:
                v_min = min(e[i])
                v_max = max(e[i])
            if v_min > min(e[i]):
                v_min = min(e[i])
            if v_max < max(e[i]):
                v_max = max(e[i])
            if prints:
                print("\ncurrent min:", v_min, ", current max:", v_max)

    if prints:
        print("actual min:", v_min, "rounded min", my_floor(v_min, 10))
        print("actual max:", v_max, "rounded max", my_ceil(v_max, 10))

    return my_floor(v_min, round_val), my_ceil(v_max, round_val)


def determine_parameters(filename, outliers):
    if filename == 'random_fixed_len_pws_RAW.csv':
        if outliers:
            return 'random_fixed_len_pw_OL.pdf', ['Average Fixed Length Password - Encryption Performance']
        return 'random_fixed_len_pw.pdf', ['Average Fixed Length Password - Encryption Performance']
    elif filename == 'random_random_len_pws_RAW.csv':
        if outliers:
            return 'random_random_len_pw_OL.pdf', ['Average Random Length Password - Encryption Performance']
        return 'random_random_len_pw.pdf', ['Average Random Length Password - Encryption Performance']
    elif filename == 'single_fixed_len_pw_RAW.csv':
        if outliers:
            return 'single_fixed_len_pw_OL.pdf', ['Single Fixed Length Password - Encryption Performance']
        return 'single_fixed_len_pw.pdf', ['Single Fixed Length Password - Encryption Performance']
    elif filename == 'single_fixed_len_pw_new_strings_RAW.csv':
        if outliers:
            return 'single_fixed_len_pw_string_refresh_OL.pdf', ['Single Fixed Length Password, \nVarying Strings '
                                                                 '- Encryption Performance']
        return 'single_fixed_len_pw_string_refresh.pdf', ['Single Fixed Length Password, \nVarying Strings '
                                                          '- Encryption Performance']
    else:
        # unknown case
        return 'unknown.pdf', ['Encryption Performance']


def create_single_boxplot(filename, show_outliers=False, force_y_axis=None, fixed_axis=True, prints=False):
    if force_y_axis is None:
        force_y_axis = [None, None]
    # get data
    sizes, encrypted = import_data(filename)
    # grab case-dependent parameter values
    plt.rcParams.update({'font.size': 20})
    fig_name, legend_labels = determine_parameters(filename, show_outliers)
    # get y label range => NOTE: abandoned, detection does not work due to outliers
    # y_min, y_max = determine_y_axis_range(prints=prints)

    # manage labels
    sizes.insert(0, '')
    labels = sizes

    # create boxplot
    x = np.arange(len(labels))
    fig, ax = plt.subplots()

    medianprops = dict(linewidth=2, color='black')
    boxprops = dict(facecolor="xkcd:light blue")
    bp = ax.boxplot(encrypted, patch_artist=True,
                    showfliers=show_outliers, medianprops=medianprops,
                    boxprops=boxprops)

    # manage axis
    ax.set_ylabel('Runtime [ms]')
    ax.set_xlabel('Input Size [Bytes]')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend([bp["boxes"][0]], legend_labels, loc="upper left")
    ax.set_axisbelow(True)
    ax.grid(color='xkcd:light grey')

    # y axis limit if option is set
    if fixed_axis:
        ax.set_ylim(force_y_axis)

    # figure settings
    fig.set_figheight(8)
    fig.set_figwidth(12)
    plt.gcf().set_facecolor('white')
    fig.tight_layout()
    plt.savefig(fig_name, format='pdf')

    plt.show()


def create_comparative_boxplot(show_outliers=True, prints=False):
    # NOTE: hardcoded the files for this one
    # import data
    sizes, sf = import_data('single_fixed_len_pw_RAW.csv', prints)
    _, sfr = import_data('single_fixed_len_pw_new_strings_RAW.csv', prints)
    _, rf = import_data('random_fixed_len_pws_RAW.csv', prints)
    _, rr = import_data('random_random_len_pws_RAW.csv', prints)

    # define legend labels (NOTE: hardcoded)
    plt.rcParams.update({'font.size': 16})
    legend_labels = [
        "Single Fixed Length Password",
        "Single Fixed Length Password, Varying Strings",
        "Random Fixed Length Password (avg)",
        "Random Random Length Password (avg)"
    ]

    # determine name
    if show_outliers:
        name = "comparative_password_performance_OL.pdf"
    else:
        name = "comparative_password_performance.pdf"

    # define labels
    lengths = copy.deepcopy(sizes)
    lengths.insert(0, '')
    lengths.append('')
    labels = lengths

    # handle positioning and widths
    x = (6 * np.arange(len(labels))) - 3.5

    n = len(sizes)
    m = len(legend_labels)  # "=" number of files
    grouping_space = 2
    k = m+grouping_space
    p_sf = [1+(k*i) for i in range(n)]
    p_sfr = [2+(k*i) for i in range(n)]
    p_rf = [3+(k*i) for i in range(n)]
    p_rr = [4+(k*i) for i in range(n)]
    print(p_sf, p_sfr)

    # create plot
    fig, ax = plt.subplots()

    medianprops = dict(linewidth=1, color='black')
    # boxes
    bp_sf = ax.boxplot(sf, patch_artist=True, positions=p_sf,
                       showfliers=show_outliers, medianprops=medianprops,
                       boxprops=dict(facecolor="xkcd:light blue"))

    bp_sfr = ax.boxplot(sfr, patch_artist=True, positions=p_sfr,
                        showfliers=show_outliers, medianprops=medianprops,
                        boxprops=dict(facecolor="xkcd:blue"))

    bp_rf = ax.boxplot(rf, patch_artist=True, positions=p_rf,
                       showfliers=show_outliers, medianprops=medianprops,
                       boxprops=dict(facecolor="xkcd:light grey"))

    bp_rr = ax.boxplot(rr, patch_artist=True, positions=p_rr,
                       showfliers=show_outliers, medianprops=medianprops,
                       boxprops=dict(facecolor="xkcd:grey"))

    # axis labels and ticks
    ax.set_ylabel('Runtime [ms]')
    ax.set_xlabel('Input Size [Bytes]')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend([bp_sf["boxes"][0], bp_sfr["boxes"][0], bp_rf["boxes"][0],
               bp_rr["boxes"][0]], legend_labels, loc='upper left')
    ax.set_axisbelow(True)

    # plt.style.use('grayscale')
    ax.grid(color='xkcd:light grey')
    fig.set_figheight(8)
    fig.set_figwidth(12)
    plt.gcf().set_facecolor('white')
    fig.tight_layout()
    plt.savefig(name, format='pdf')

    plt.show()


y_axis_range = [155, 195]
create_single_boxplot('random_fixed_len_pws_RAW.csv', force_y_axis=y_axis_range)
create_single_boxplot('random_random_len_pws_RAW.csv', force_y_axis=y_axis_range)
create_single_boxplot('single_fixed_len_pw_RAW.csv', force_y_axis=y_axis_range)
create_single_boxplot('single_fixed_len_pw_new_strings_RAW.csv', force_y_axis=y_axis_range)
create_comparative_boxplot(show_outliers=False)
create_comparative_boxplot()

exit(0)
