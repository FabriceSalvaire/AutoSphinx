# A source code comment
#?# A comment that must not appear in the documentation

foo = 1

#!# ==========================
#!#  A Restructuredtext Title
#!# ==========================

foo = 1

#!#
#!# Some reStructuredText contents
#!#

foo = 1

# Insert the output of the following python code
print(foo)
#o#

foo = 1

# Hidden Python code
#h# value = 123 * 3

foo = 1

#!# Format RST content with current locals dictionary using @@<<@@...@@>>@@ instead of {...}.
#!#
#!# .. math::
#!#
#!#     I_d = @<@value@>@ I_s \left( e^{\frac{V_d}{n V_T}} - 1 \right)

# Add Python code as a literal block
#l# for x in ():
#l#   1 / 0 / 0

# Guarded error
#<e#
1/0
#e>#

# Add a Python file as a literal block
#i# RingModulator.py

# Add the file content as literal block
#itxt# kicad-pyspice-example.cir

# Insert an image
#lfig# kicad-pyspice-example.sch.svg

# Insert Circuit_macros diagram
#cm# circuit.m4

# Insert Tikz figure
#tz# diode.tex

import numpy as np
import matplotlib.pyplot as plt
figure = plt.figure(1, (20, 10))
x = np.arange(1, 10, .1)
y = np.sin(x)
plt.plot(x, y)

# Insert a Matplotlib figure
#fig# save_figure(figure, 'my-figure.png')

foo = 1
