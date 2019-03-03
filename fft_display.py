import numpy as np
import matplotlib.pyplot as plot
from scipy import signal

Fs = 46242
#adc 1 us
f= 10000
seconds= 1

amp = 3.3
t = np.linspace(0, seconds, Fs)

#x1= amp*np.sin(2*np.pi*f*t);
#x2= amp*signal.square(2*np.pi*f*t);
x3 = amp

# plot the signal in frequency domain
#plot.plot(t, x1)
#plot.plot(t, x2)
plot.magnitude_spectrum(x3,Fs=Fs)
# display the plots
plot.show()