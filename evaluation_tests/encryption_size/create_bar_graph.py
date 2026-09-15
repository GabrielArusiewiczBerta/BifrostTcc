import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from evaluation_tests.encryption_size.generate_encryption_size_data import generate_encryption_size_data

_, normal_bytes, _, encrypted_bytes, increase_percentage = generate_encryption_size_data(prints=True)
plt.rcParams.update({'font.size': 16})
labels = normal_bytes

x = np.arange(len(labels))  # the label locations
width = 0.35  # the width of the bars

fig, ax = plt.subplots()

kwargs = {"hatch":'xxxxxx'}  
rects1 = ax.bar(x - width/2, normal_bytes, width, label='Unencrypted', color='w', edgecolor='k',  **kwargs)  
 
#kwargs = {"hatch":'.'}  
    
kwargs = {"hatch":'//////'}  
rects2 = ax.bar(x + width/2, encrypted_bytes, width, label='Encrypted', color='w', edgecolor='k', **kwargs) 

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Output Size [Bytes]')
ax.set_xlabel('String Size [Bytes]')
#ax.set_title('Encryption Overhead')

ax.set_xticks(x)
ax.set_xticklabels(labels)
#ax.set_yticks(encrypted_bytes)

ax.legend()
ax.set_axisbelow(True)
ax.grid()

def autolabel(rects):
    """Attach a text label above each bar in *rects*, displaying its height."""
    i = 0
    for rect in rects2:
        percentage = increase_percentage[i]
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


autolabel(rects1)
autolabel(rects2)

fig.set_figheight(8)
fig.set_figwidth(12)

fig.tight_layout()
fig.savefig("encryption-data-size.pdf", format="pdf")


plt.show()
exit(0)
