# Bugs


# Bug 1

I launched the Swift browser, tried to pull the tab out of Safari into its own window, and it crashed.  
Accidently dropped it into another Safari window under a differnt profile, pulled it of there
and it was non responsive.  I had to ^C it.


I did a stupid thing, but it shouldn't have hung.

```
In [27]: env.launch(realtime=True)
^C---------------------------------------------------------------------------
KeyboardInterrupt                         Traceback (most recent call last)
Cell In[27], line 1
----> 1 env.launch(realtime=True)

File ~/Library/CloudStorage/Dropbox/code/swift/src/swift/Swift.py:269, in Swift.launch(self, realtime, headless, rate, browser, axes, **kwargs)
    264 self.last_time = time.time()
    266 # The realtime, render and pause buttons -- added after the
    267 # browser has connected, since sending them any earlier would
    268 # block waiting for a reply from a client that isn't there yet.
--> 269 self._add_controls()
    271 if not self.axes:
    272     self._send_socket("axes", False, expected=False)

File ~/Library/CloudStorage/Dropbox/code/swift/src/swift/Swift.py:954, in Swift._add_controls(self)
    952 self._pause_button = Button(self._pause_control, desc="||")
    953 self._pause_button.builtin = True
--> 954 self.add_ui(self._pause_button)
    956 # self.realtime_speed may be an arbitrary float set directly via
    957 # launch(realtime=<float>) rather than one of the dropdown presets
    958 # -- fall back to "Max" in the display without touching the actual
    959 # (still fully respected) speed.
    960 try:

File ~/Library/CloudStorage/Dropbox/code/swift/src/swift/Swift.py:550, in Swift.add_ui(self, element, name)
    547 element._id = id
    549 if not self.headless:
--> 550     self._send_socket("element", element.to_dict())
    551 return element

File ~/Library/CloudStorage/Dropbox/code/swift/src/swift/Swift.py:924, in Swift._send_socket(self, code, data, expected)
    921 self.outq.put(msg)
    923 if expected:
--> 924     return self.inq.get()
    925 else:
    926     return "0"

File ~/opt/miniconda3/envs/dev/lib/python3.12/queue.py:171, in Queue.get(self, block, timeout)
    169 elif timeout is None:
    170     while not self._qsize():
--> 171         self.not_empty.wait()
    172 elif timeout < 0:
    173     raise ValueError("'timeout' must be a non-negative number")

File ~/opt/miniconda3/envs/dev/lib/python3.12/threading.py:355, in Condition.wait(self, timeout)
    353 try:    # restore state no matter what (e.g., KeyboardInterrupt)
    354     if timeout is None:
--> 355         waiter.acquire()
    356         gotit = True
    357     else:

KeyboardInterrupt: 
```

# Bug 2

It hung when I added the gripper mesh to the scene.  I had to ^C it.

```
In [6]: sphere = gm.Sphere(0.3, pose=SE3(2, 0, 0.3), color="red")

In [7]: cube = gm.Cuboid([1, 1, 1], pose=SE3(0, 0, 0.5), color="blue")

In [8]: gripper = gm.Mesh("../figs/panda_hand.dae", pose=SE3.Rx(90, unit="deg"))

In [9]: env.add(cube)
Out[9]: 0

In [10]: env.add(sphere)
Out[10]: 1

In [11]: env.add(gripper)
^C---------------------------------------------------------------------------
KeyboardInterrupt                         Traceback (most recent call last)
Cell In[11], line 1
----> 1 env.add(gripper)

File ~/Library/CloudStorage/Dropbox/code/swift/src/swift/Swift.py:470, in Swift.add(self, ob, robot_alpha, collision_alpha, readonly, name)
    438 """
    439 Add an object to the graphical scene
    440 
   (...)    466 :rtype: int | AssemblyHandle | SwiftElement
    467 """
    469 if isinstance(ob, Shape):
--> 470     return self.add_shape(ob, name=name)
    471 elif isinstance(ob, SwiftElement):
    472     return self.add_ui(ob, name=name)

File ~/Library/CloudStorage/Dropbox/code/swift/src/swift/Swift.py:506, in Swift.add_shape(self, shape, callback, name)
    503     id = int(self._send_socket("shape", [shape.to_dict()]))
    505     while not int(self._send_socket("shape_mounted", [id, 1])):
--> 506         time.sleep(0.1)
    508 else:
    509     id = len(self.swift_objects)

KeyboardInterrupt: 
```

Again, shouldn't have hung, I just added a mesh to the scene.  It worked fine with the cube and sphere.