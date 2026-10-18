// The guards at the moat's toll gate (their model: art/blender/guards.py),
// one either side of the way to the drawbridge, their halberds grounded
// beside them. They stand easy, watching you: their heads turn to you as
// you come near. Paid the penny, the one nearer you reaches out to take it,
// and the other gives you a thumbs-up.
//
// Their clips are the Universal Animation Libraries', named as they are there.

import {
  type AnimationAction,
  type AnimationClip,
  AnimationMixer,
  LoopOnce,
  Mesh,
  type Object3D,
  Quaternion,
  type Scene,
  Vector3,
} from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

import type { Circle, Ground } from "./player";

const TALL = 1.04; // times the size they're made
const BODY = 0.38; // metres: their radius, for bumping into them
const HEAD = 2.0; // metres: their height
const BLEND = 0.3; // seconds from one clip to the next
const WATCH = 14; // metres: this near, they watch you
const TURN = 1.1; // radians their heads turn, at most, either way
const LIFT = 0.18; // radians their heads are lifted from the clip's (looking down), and up to you
const THANKS = 0.9; // seconds after the one takes the penny, the other's thumbs-up
const UP = new Vector3(0, 1, 0);
const ACROSS = new Vector3(1, 0, 0);

interface Guard {
  model: Object3D;
  head: Object3D | undefined;
  mixer: AnimationMixer;
  clips: Map<string, AnimationAction>;
  playing: AnimationAction | undefined;
  /** Seconds, till its clip played once is done (then it stands easy again). */
  busy: number;
  /** Seconds, till it's to give a thumbs-up. */
  thanks: number;
  yaw: number;
  look: { turn: number; up: number };
  body: Circle;
}

export class Guards {
  private guards: Guard[] = [];
  /** Where they are, solid (player.movers). */
  readonly bodies: Circle[] = [];

  constructor(scene: Scene, source: Object3D, clips: AnimationClip[], spots: number[][], ground: Ground) {
    spots.forEach(([x, z], k) => {
      const model = clone(source);
      model.traverse((o) => {
        if (o instanceof Mesh) {
          o.castShadow = true;
          o.frustumCulled = false; // (moved by their bones: their bounds don't follow)
        }
      });
      // (A beard on one of them only.)
      const beard = model.getObjectByName("guard-beard");
      if (beard) beard.visible = k === 1;
      model.scale.setScalar(TALL);
      // Facing up the path, turned a little to the way between them.
      const yaw = Math.atan2(-Math.sign(x) * 0.3, -1);
      model.position.set(x, ground(x, z) ?? 0, z);
      model.rotation.y = yaw;
      scene.add(model);
      const mixer = new AnimationMixer(model);
      const actions = new Map(clips.map((clip) => [clip.name, mixer.clipAction(clip)]));
      for (const name of ["Interact", "Yes"]) actions.get(name)?.setLoop(LoopOnce, 1);
      const body = { x, z, r: BODY, top: model.position.y + HEAD };
      const guard: Guard = {
        model,
        head: model.getObjectByName("Head"),
        mixer,
        clips: actions,
        playing: undefined,
        busy: 0,
        thanks: 0,
        yaw,
        look: { turn: 0, up: 0 },
        body,
      };
      this.play(guard, "Idle_Loop");
      // (Not in step with each other.)
      mixer.update(k * 1.3);
      this.guards.push(guard);
      this.bodies.push(body);
    });
  }

  private play(guard: Guard, name: string) {
    const next = guard.clips.get(name);
    if (!next || next === guard.playing) return;
    next.reset().play();
    if (guard.playing) next.crossFadeFrom(guard.playing, BLEND, false);
    guard.playing = next;
    guard.busy = next.loop === LoopOnce ? next.getClip().duration - BLEND : 0;
  }

  /** The penny's paid: the one nearer you takes it, and the other thanks you. */
  pay(you: Vector3) {
    const [nearer, other] = [...this.guards].sort(
      (a, b) => a.model.position.distanceTo(you) - b.model.position.distanceTo(you)
    );
    if (nearer) this.play(nearer, "Interact");
    if (other) other.thanks = THANKS;
  }

  /** Each frame: where your eyes are. */
  update(dt: number, eye: Vector3) {
    for (const guard of this.guards) {
      if (guard.thanks > 0) {
        guard.thanks -= dt;
        if (guard.thanks <= 0) this.play(guard, "Yes");
      }
      if (guard.busy > 0) {
        guard.busy -= dt;
        if (guard.busy <= 0) this.play(guard, "Idle_Loop");
      }
      guard.mixer.update(dt);
      this.watch(guard, eye, dt);
    }
  }

  /** Its head turned to you, near enough (as far as it can turn). */
  private watch(guard: Guard, eye: Vector3, dt: number) {
    const { head, model, look } = guard;
    if (!head?.parent) return;
    model.updateMatrixWorld(true);
    const at = head.getWorldPosition(new Vector3());
    const dx = eye.x - at.x;
    const dz = eye.z - at.z;
    const far = Math.hypot(dx, dz);
    let turn = Math.atan2(dx, dz) - guard.yaw;
    turn = Math.atan2(Math.sin(turn), Math.cos(turn));
    const watching = far < WATCH && Math.abs(turn) < TURN + 0.6;
    const wants = {
      turn: watching ? Math.max(-TURN, Math.min(TURN, turn)) : 0,
      up: LIFT + (watching ? Math.max(-0.3, Math.min(0.35, Math.atan2(eye.y - at.y, far))) : 0),
    };
    const ease = Math.min(1, dt * 3);
    look.turn += (wants.turn - look.turn) * ease;
    look.up += (wants.up - look.up) * ease;
    // (Turned in the guard's own frame, on top of what its clip does: round,
    // then up, and back into the head's parent's.)
    const facing = model.getWorldQuaternion(new Quaternion());
    const turned = new Quaternion()
      .setFromAxisAngle(UP, look.turn)
      .multiply(new Quaternion().setFromAxisAngle(ACROSS, -look.up));
    const world = head.getWorldQuaternion(new Quaternion());
    const wanted = facing.clone().multiply(turned).multiply(facing.clone().invert()).multiply(world);
    head.quaternion.copy(head.parent.getWorldQuaternion(new Quaternion()).invert().multiply(wanted));
  }
}
