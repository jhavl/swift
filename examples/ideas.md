I'm noodling around with some ways of expressing what I want to using Swift.  I like to start with what
I want as a user, then work backwards to the implementation. 

Here's me sketching off two of our examples.

# box_orbit example

```
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True)

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0.1), color=[0.2, 0.4, 1.0, 1.0])
env.add(box)

while True:
    box.T = sm.SE3.Rx(t / 10) * sm.SE3.Rz(t) * sm.SE3.Tx(3 * W)

    t += dt
    env.step(dt)
    time.sleep(dt)
```

Alternatively we could use callbacks to make this all more succinct.

```
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift

env = Swift()
env.launch(realtime=True)

box = sg.Cuboid([0.2, 0.2, 0.2], pose=SE3(0, 0, 0.1), color=[0.2, 0.4, 1.0, 1.0])
env.add(box, lambda t: box.T = SE3.Rx(t / 10) * SE3.Rz(t) * SE3.Tx(3 * W))

while True:

    env.step(dt) # the env should hold t and this step should increment it and call the callback with the new t
    # time.sleep(dt)  realtime=True should already do this
```

added the idea of a callback to avoid having to explicitly stepping the env.  Could be done in
a backward compatible way.

# two link example

A more complex example

```
import time
import numpy as np
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift, Slider
from swift.Handle import SwiftPart


class TwoLinkArm:
    """A pure kinematic model: two links, two revolute joints about z."""

    def __init__(self, L1=0.3, L2=0.25, thickness=0.03):
        self.L1 = L1
        self.L2 = L2
        self.link1 = sg.Cuboid([L1, thickness, thickness], color=[0.8, 0.2, 0.2, 1.0])
        self.link2 = sg.Cuboid([L2, thickness, thickness], color=[0.2, 0.4, 1.0, 1.0])

    def part_poses(self, q) -> list[SE3]:
        """World pose of each link, purely as a function of q. Each
        cuboid's local origin sits at its own proximal (joint) end, so
        Tx(length / 2) places its centre correctly."""
        joint1 = SE3.Rz(q[0])
        joint2 = joint1 * SE3.Tx(self.L1) * SE3.Rz(q[1])
        return [joint1 * SE3.Tx(self.L1 / 2), joint2 * SE3.Tx(self.L2 / 2)]


class ArmHandle:
    """Owns this instance's live joint state -- the role RobotHandle plays
    for an rtb.Robot, minus everything RTB-specific."""

    def __init__(self, arm):
        self.arm = arm
        self.q = np.zeros(2)

    def part_poses(self) -> list[SE3]:
        return self.arm.part_poses(self.q)


arm = TwoLinkArm()
handle: SwiftPart = ArmHandle(arm)

# ArmHandle never inherits from SwiftPart -- it conforms just by having a
# matching part_poses() method. This is the same structural contract
# RobotHandle satisfies for an rtb.Robot, checkable at runtime because
# SwiftPart is declared @runtime_checkable:
assert isinstance(handle, SwiftPart)

env = Swift()
env.launch(realtime=True)
env.add(arm.link1)
env.add(arm.link2)


def set_q1(v):
    handle.q[0] = float(v)


def set_q2(v):
    handle.q[1] = float(v)


env.add(Slider(set_q1, min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 1", unit="rad"))
env.add(Slider(set_q2, min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 2", unit="rad"))

while True:
    arm.link1.T, arm.link2.T = handle.part_poses()
    env.step(0.05)
    time.sleep(0.05)
```

this has too many lines of code for my liking.

Alternatively

```
import time
import numpy as np
import spatialgeometry as sg
from spatialmath import SE3
from swift import Swift, Slider


env = Swift()
env.launch(realtime=True)

link1 = sg.Cuboid([L1, thickness, thickness], color=[0.8, 0.2, 0.2, 1.0])
link2 = sg.Cuboid([L2, thickness, thickness], color=[0.2, 0.4, 1.0, 1.0])


def fk(self, q) -> list[SE3]:
    """World pose of each link, purely as a function of q. Each
    cuboid's local origin sits at its own proximal (joint) end, so
    Tx(length / 2) places its centre correctly."""
    joint1 = SE3.Rz(q[0])
    joint2 = joint1 * SE3.Tx(self.L1) * SE3.Rz(q[1])
    return [joint1 * SE3.Tx(self.L1 / 2), joint2 * SE3.Tx(self.L2 / 2)]

# introduce the idea of an "assembly" of parts, simply a list of parts and a function to assemble them in space
# add_assembly(fk_function, list of assembly parts, env callback)
# maybe a name parameters as well for debugging, env.list(), env.show()

arm = swift.add_assembly(fk, [link1, link2], callback=lambda t, values: fk(values["q1"], values["q2"])

# if there's a UI, that gets passed as a dict to the assembly, the dict name is the last arg below
env.add(Slider(min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 1", unit="rad"), name="q1")
env.add(Slider(min=-np.pi, max=np.pi, step=0.01, value=0.0, desc="Joint 2", unit="rad"), name="q2")

while True:
    env.step(0.05)
    # time.sleep(0.05) # realtime=True should already do this

# or even

env.run(10, 0.05)
```

alternatively

```
arm = swift.add_assembly(fk, [link1, link2], callback=lambda t, values: fk(values["q1"], values["q2"])

while True:
    arm.q = q_value
    arm.set_q(q_value)
    env.step(0.05)
```

# RTB integration

The question is do we allow

```
env.add(rtb_robot)
```

which means swift needs to know about RTB, lazy or not.  Or do we do a bit of work on the outside

```
env.add_assembly(rtb_robot.fkine_all, rtb_robot.links)
```

# Claude's critique / response (2026-07-29)

Read all of the above. Reacting point by point, then a proposed synthesis.

## box_orbit callback

The idea (swift owns `t`, invokes a callback each step instead of the user
manually mutating `box.T` in a loop) is good and cuts real boilerplate. Two
fixes needed on the sketch itself:

- `lambda t: box.T = SE3.Rx(...)` isn't valid Python -- assignment isn't an
  expression, can't live inside a lambda.
- More than a syntax fix: the callback should **return** the pose rather
  than mutate `box.T` itself -- `env.add(box, lambda t: SE3.Rx(t/10) *
  SE3.Rz(t) * SE3.Tx(3*W))`, swift assigns the result to `box.T`. Same
  reason we've leaned pure-function everywhere else this session
  (`fkine_geometry(q)`, `part_poses(q)`) -- a callback that returns a value
  is testable in isolation and has one obvious contract, a callback that
  reaches out and mutates a captured variable doesn't.

Backward compatible, as you said -- the existing manual `while True: box.T
= ...; env.step(dt)` form doesn't go away, this is purely additive.

Peter: cut and paste laziness on my part.  The idea of not mutating is attractive.

## two_link example -- agreed, too many lines

You're right and this validates something I flagged last turn independently:
`ArmHandle` is boilerplate every conforming object has to hand-write (q/qd
storage, a `part_poses()` forwarding method) for no real benefit. Your
`add_assembly(fk, parts, callback=...)` sketch is a better answer than what
I'd proposed (a `Chain` class with a `.add_link()` builder) -- it needs no
new class *or* builder API, just a bare function + the parts list, which is
strictly less to learn and less to write. I'm dropping my `Chain`-class idea
in favour of this.



One correction on the RTB line specifically (see below): `fk` should have
signature `fk(q) -> list[SE3]` -- the `self` in the sketch's earlier `def
fk(self, q)` looks like copy-paste residue from the class version just
above it, not intentional.

Peter: Yes

## The `values` dict idea generalizes further than assemblies

Named UI elements (`name="q1"`) collected into a `values` dict and handed
to a per-step callback removes the `def set_x(x): pos[0] = x` boilerplate
that's currently in *every* slider-driven example (`box_sliders.py`,
`panda_ik_sliders.py`, not just the assembly ones). Worth treating as its
own change, not scoped only to `add_assembly` -- `env.step()` could hand
`values` to *any* registered per-step callback, assembly or plain shape.

One thing to settle: box_orbit's callback is `(t)`, add_assembly's is `(t,
values)`. Should be one contract, always `(t, values)` -- box_orbit-style
callbacks just ignore `values` (empty dict when nothing's bound to them).

Peter: agree with the contract.  Will simplify all examples.  I have a pathological 
hatred of boilerplate and cruft.

## `add_assembly` vs. the Protocol I proposed last turn

Given `add_assembly` takes a bare callable, I don't think we need a
`ChainModel`-style Protocol at the *model* level after all -- that was
solving the same problem your sketch solves more simply. The Protocol
still earns its keep at the *handle* level though: whatever `add_assembly`
returns (`arm` in your sketch) still needs a uniform contract so
`Swift.step()`/`_draw_all()` can drive it the same way regardless of how
it was constructed -- that's still `SwiftPart`'s zero-arg `part_poses()`,
already implemented and `@runtime_checkable`.

Which raises a design question worth deciding explicitly: should
`add_assembly(...)` and `env.add(rtb_robot)` return **the same handle
class**? I think yes -- one generic handle (`q`/`qd`/`control_mode`,
computed via a stored `fk` callable) regardless of entry point, not a
`RobotHandle` and a separate `AssemblyHandle` that happen to look alike.
See below.

Peter: One generic handle is the design win, a unification!  It's impedance matching between specialist
robot class and a more general assembly of things we want to draw.  This is a first step
on pulling all the SG stuff from links and robots.

## RTB integration -- I'd reframe this as layering, not choosing

Read this as an either/or (`env.add(rtb_robot)` *or* push the work to the
caller) but I don't think it has to be. Proposal: `add_assembly` is the one
real mechanism; `env.add(rtb_robot)` becomes a thin convenience special
case implemented *in terms of* it -- roughly

```
def add(self, ob, ...):
    if isinstance(ob, rtb.Robot):
        parts = [g for link in ob.links for g in link.geometry]  # + collision, + grippers
        return self.add_assembly(lambda q: ob.fkine_geometry(q, robot_alpha, collision_alpha), parts)
    ...
```

(sketch -- `fkine_all` in your example returns link *frames*, not
per-geometry-part poses; `fkine_geometry` is the one that already lines up
1:1 with a flattened parts list, alpha-gating included.)

Why layer instead of picking one: the "push work to the caller" version's
actual cost is smaller than it looks, because `parts` just needs to be the
existing live `Shape` objects off `robot.links[i].geometry` -- each one
already knows how to serialize its own initial mount message
(`Shape.to_dict()`), same as any individually-`env.add()`-ed shape today.
So there's no bespoke RTB-side serialization to invent, just a flatten.
That means the "special case" is genuinely thin (a few lines gluing
`fkine_geometry` + a flattened parts list into `add_assembly`), stays
behind the same lazy `_import_rtb()` swift already uses today, and a
beginner still gets `env.add(panda)` working with no extra import. Purity
("swift's core should know nothing about RTB") is nice in principle, but
the lazy-import discipline already delivers the thing that actually
matters (no hard dependency, Pyodide wheel doesn't need RTB) -- so I'd
rather keep the ergonomic one-liner and make it thin, not delete it.

Peter: if we already have add(sg_prim) for a part, add_assembly(), then should we
just have add_robot(), easier to read and no type checking required.

## `env.run(duration, dt)`

Separate, smaller idea, worth keeping on the table but not blocking on:
removes the last bit of loop boilerplate for the fully-automatic case.
Needs its own small decision later -- is `duration` seconds of sim time or
a step count, and how does it interact with the existing pause button /
`realtime_speed` control (does pausing in the browser pause `env.run()`,
or are they unrelated)?

Peter: could its meaning depend on `realtime` value?  Need to discuss more.

## `arm.q = q_value`

Matches what's already built (`RobotHandle.q` as a plain settable
attribute) -- no change needed, just confirms the direction.

## Naming

You used "assembly" unprompted, which is a real signal -- it might be a
better generic term than "Chain"/"ChainHandle" from last turn's naming
discussion (avoids overloading a robotics-specific word, and reads fine
for a two-link arm just as well as a Panda). If we go this way it'd be
`add_assembly()` / `AssemblyHandle` (or similar), not `Chain`/`ChainHandle`.
Worth deciding this alongside everything else above rather than separately.

Peter: I've thought long and hard about the name and I think assembly is right in this case.  Has
some precedence in the CAD world also.

# Claude, round 2 (2026-07-29)

Good, that settles the naming and the big design calls. Two things worth
answering before this is ready to crystallize into a plan.

## "first step on pulling all the SG stuff from links and robots"

Worth saying plainly: I read this as the actual throughline connecting
everything this session -- `fkine_geometry` (pure FK, bypasses SceneNode),
the handle owning `q` instead of the model, and now `assembly` as the
generic "parts + a way to pose them" concept. Long-term horizon this
points at: `Robot`/`Link` stop carrying `.geometry`/SceneNode duties at
all, and become pure kinematic specification (ETS/DH, joint limits) --
geometry attachment and rendering live entirely on the swift/assembly
side. `add_robot()`'s adapter (flattening `link.geometry` into a parts
list) still reads geometry off `Link` today, so it's not that move yet --
but it's the shape of the seam where that move would eventually happen.
Not proposing we do that now, just naming it so we're deciding today's
smaller steps with that destination in view rather than by accident.

Peter: it's consistent with the desiderata and I'd value your take on that.  Mesh/shape
data is part of the link, but it's a passive carrier, not an active participant in visualization.

## `add_robot()` instead of isinstance dispatch in `add()`

Agree, and I'd take it one step further: if `add_robot()` exists, `add()`
should probably *stop* accepting an `rtb.Robot` at all (no silent
isinstance fallback) -- one explicit entry point per kind of thing, no
type-checking branch left to maintain or misroute into. Concretely three
top-level methods: `add(shape)`, `add_assembly(fk, parts, ...)`,
`add_robot(robot, ...)` -- the latter two both returning the one generic
handle.

Question this raises: does `add()` keep doing isinstance dispatch between
`Shape` and `SwiftElement` (it currently handles both), or does that split
too (`add_element()` alongside `add(shape)`)? You only called out the
shape/assembly/robot triad -- want that split as well, or is
Shape+SwiftElement together in `add()` fine since both are "one simple
thing," with the isinstance branching you're objecting to really being
about the *robot* case specifically (heavier, more special-cased) rather
than isinstance-dispatch in general?

Peter: this is for Swift UI elements. Messy idea, but maybe helpful for back compat.
we keep add() with a type if tree (the past), but have add_primitive, add_ui methods etc. (the future).

## Naming still open: the handle class itself

`add_assembly`/`add_robot` as verbs are settled. The thing they return
isn't named yet. Given it's now the *one* generic handle (assemblies and
robots both), I'd lean toward just `Handle` rather than `AssemblyHandle` --
prefixing it with "Assembly" reads oddly once `add_robot()` returns one
too. Lives in `swift/Handle.py` already, so `from swift import Handle`
reads fine. Object to that, or is there a better name?

Peter: I'd prefer AssemblyHandle, it's how Swift is interpretting the robot, it's now firmly
in the Swift realm.