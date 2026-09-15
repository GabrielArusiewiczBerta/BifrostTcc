import matplotlib.pyplot as plt
import numpy as np
from evaluation_tests.encryption_performance.extract_data import extract_data_from_csv


sizes, unencrypted, encrypted, increase = extract_data_from_csv(True)
labels = sizes

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots()

# "left" bar
kwargs = {"hatch": 'xxxxxx'}
rects1 = ax.bar(x - width/2, unencrypted, width, label='Unencrypted', color='w',
                edgecolor='k', **kwargs)

# "right* bar
kwargs = {"hatch": '//////'}
rects2 = ax.bar(x + width/2, encrypted, width, label="Encrypted", color="w",
                edgecolor="k", **kwargs)

# axis labels
ax.set_ylabel('Runtime [ms]')
ax.set_xlabel('Input Size [Bytes]')

# axis ticks
ax.set_xticks(x)
ax.set_xticklabels(labels)

# axis settings
ax.legend()
ax.set_axisbelow(True)
ax.grid()

def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    i = 0
    for rect in rects2:
        percentage = increase[i]
        height = rect.get_height()
        i+=1
        ax.annotate('{}%'.format(int(percentage)),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    rotation=25.,
                    weight='medium',
                    size=11,
                    ha='center', va='bottom')


# autolabel(rects1)
# autolabel(rects2)
# NOTE: i like it better without the percentages

fig.set_figheight(8)
fig.set_figwidth(12)

fig.tight_layout()
fig.savefig("encryption_performance.pdf", format="pdf")

plt.show()
exit(0)
