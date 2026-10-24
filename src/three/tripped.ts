// Going on from the crossroads in the dark tunnels into the dark, with no
// lamp: "You fall over in the dark." You feel your way on, a few unsure
// steps into the black; your foot catches on something and you topple
// forward, bump, onto the floor. You lie there a moment, then roll over onto
// your back, looking up into the dark, and little cartoon stars circle round
// over your head, twinkling (Stars). The curtain comes down over the end of
// it (from a little before `ends`), and they go on circling behind it.

import {
  CanvasTexture,
  Euler,
  type PerspectiveCamera,
  Quaternion,
  type Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  Vector3,
} from "three";

// The scene's beats, in seconds from walking into it.
const TRIP = 0.75; // your foot catches
const DOWN = 1.3; // on the floor, face down: bump
const ROLL = 2; // rolling over
const ROLLED = 2.9; // on your back: the stars come
const ENDS = 7;

const STEPS = 2; // unsure steps on into the dark, before it
const ON = 0.8; // metres, those steps
const TOPPLED = 0.8; // and further, falling
const EYE = 1.65; // your eye above the floor, standing
const FACE = 0.3; // face down
const BACK = 0.24; // on your back
const ROLLING = 0.35; // metres to one side, rolling over
const PEERING = -0.2; // looking down a little, feeling your way (radians)
const FLOORWARD = -Math.PI / 2 + 0.3; // looking at the floor, fallen

/** Where to find the floor (underground), at a spot. */
type Floor = (x: number, z: number) => number | undefined;

export class Tripped {
  readonly ends = ENDS;
  private t = 0;
  private readonly from: Vector3; // your eye, where you were when you came to it
  private readonly facing: Quaternion;
  private readonly floor: number; // under you, there
  private readonly ahead: Vector3; // on into the dark, the way you fall
  private readonly across: Vector3; // to your left, the way you roll
  private readonly yaw: number;
  private readonly start: Vector3; // your feet, on its way, once you've turned to it
  private readonly eye = new Vector3();
  private readonly look = new Quaternion();
  private readonly down = new Quaternion(); // face down
  private readonly turn = new Quaternion();
  private readonly euler = new Euler(0, 0, 0, "YXZ");
  private readonly up = new Vector3(0, 1, 0);
  private readonly ring = new Vector3();
  private readonly ringA = new Vector3();
  private readonly ringB = new Vector3();

  constructor(
    private camera: PerspectiveCamera,
    /** The way, from land.json: [x, z, half x, half z] (across it on its longer side). */
    box: number[],
    private floorAt: Floor,
    private stars: Stars,
    private reducedMotion: boolean,
    private play: (sound: "step" | "trip" | "bump" | "dizzy") => void
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    this.floor = this.from.y - EYE;
    const [x, z, halfX, halfZ] = box;
    // (Along it: across its narrow side, on from the side you're on.)
    const alongZ = halfX > halfZ;
    this.ahead = alongZ ? new Vector3(0, 0, this.from.z < z ? 1 : -1) : new Vector3(this.from.x < x ? 1 : -1, 0, 0);
    this.across = new Vector3().crossVectors(this.up, this.ahead);
    this.yaw = Math.atan2(-this.ahead.x, -this.ahead.z);
    // (Kept in its middle, well clear of its walls.)
    this.start = this.from.clone().setY(this.floor);
    if (alongZ) this.start.x = x + Math.max(-(halfX - 1), Math.min(halfX - 1, this.from.x - x));
    else this.start.z = z + Math.max(-(halfZ - 1), Math.min(halfZ - 1, this.from.z - z));
    this.down.setFromEuler(this.euler.set(-Math.PI / 2, this.yaw, 0));
  }

  /** Each frame (on behind the curtain, too: the stars go on circling, for good). */
  update(dt: number) {
    const was = this.t;
    this.t += dt;
    const t = this.t;
    const still = this.reducedMotion;
    const crossed = (beat: number) => was < beat && t >= beat;
    if (crossed(TRIP)) this.play("trip");
    if (crossed(DOWN)) this.play("bump");
    if (crossed(ROLLED)) this.play("dizzy");

    // On, step by step, feeling your way: a surge and a dip each step.
    const s = (Math.min(t, TRIP) / TRIP) * STEPS;
    for (let n = 1; n < STEPS; n++) if (crossed((n / STEPS) * TRIP)) this.play("step");
    const stepped = (Math.floor(s) + ease(s % 1)) / STEPS;
    const feet = this.start.clone().addScaledVector(this.ahead, ON * Math.min(1, stepped));
    if (t < ROLLED) this.stars.hide();

    if (t < TRIP) {
      this.eye.copy(feet);
      this.eye.y = this.ground(feet) + EYE - (still ? 0 : 0.05 * Math.sin(Math.PI * (s % 1)));
      // (From where you were, a little at a time: onto the way.)
      this.eye.lerp(this.from, 1 - ease(t / 0.5));
      const sway = still ? 0 : Math.sin(Math.PI * s);
      this.look.setFromEuler(this.euler.set(PEERING + 0.03 * sway, this.yaw + 0.04 * sway, 0.025 * sway));
      this.camera.position.copy(this.eye);
      // (Turning to it, at first, from however you were looking.)
      this.camera.quaternion.slerpQuaternions(this.facing, this.look, ease(t / 0.4));
      return;
    }

    // Toppling forward, faster and faster, your head going over in an arc
    // to the floor.
    const f = Math.min(1, (t - TRIP) / (DOWN - TRIP));
    const k = (f * f * Math.PI) / 2;
    const fallen = feet.clone().addScaledVector(this.ahead, TOPPLED * Math.sin(k));
    const floor = this.ground(fallen);
    // (A lurch, as your foot catches, before you go.)
    const lurch = still ? 0 : 0.08 * Math.sin(Math.PI * Math.min(1, f * 3));
    if (t < ROLL) {
      this.eye.copy(fallen);
      this.eye.y = floor + FACE + (EYE - FACE) * Math.cos(k) - lurch;
      // (And a little bounce, landing.)
      if (t > DOWN && !still) this.eye.y += 0.05 * Math.sin(Math.PI * Math.min(1, (t - DOWN) / 0.25));
      const lying = ease((t - DOWN) / (ROLL - DOWN));
      const pitch = PEERING + (FLOORWARD - PEERING) * (f * f) - lurch;
      this.look.setFromEuler(
        this.euler.set(pitch + (-Math.PI / 2 - FLOORWARD) * lying, this.yaw, 0.12 * Math.sin(Math.PI * f))
      );
      this.camera.position.copy(this.eye);
      this.camera.quaternion.copy(this.look);
      return;
    }

    // Rolling over onto your back (to your left), round your body's length,
    // from looking at the floor to looking up into the dark.
    const r = ease((t - ROLL) / (ROLLED - ROLL));
    this.eye.copy(fallen).addScaledVector(this.across, ROLLING * r);
    this.eye.y = this.ground(this.eye) + FACE + (BACK - FACE) * r + 0.12 * Math.sin(Math.PI * r);
    this.look.copy(this.down).premultiply(this.turn.setFromAxisAngle(this.ahead, -Math.PI * r));
    // Dizzy, on your back: your head lolling a little, round and round.
    const dizzy = t - ROLLED;
    if (dizzy > 0 && !still) {
      const lolling = 0.07 * Math.min(1, dizzy);
      this.look.premultiply(this.turn.setFromAxisAngle(this.ahead, lolling * Math.sin(dizzy * 1.6)));
      this.look.premultiply(this.turn.setFromAxisAngle(this.across, lolling * Math.cos(dizzy * 1.6)));
    }
    this.camera.position.copy(this.eye);
    this.camera.quaternion.copy(this.look);
    if (dizzy <= 0) return;

    // The stars: round a ring tipped up over your head, the far side of it
    // higher up the picture.
    this.ring.copy(this.eye).addScaledVector(this.up, 0.75).addScaledVector(this.ahead, 0.15);
    this.ringA.copy(this.across).multiplyScalar(0.36);
    this.ringB.copy(this.ahead).multiplyScalar(0.22).addScaledVector(this.up, 0.12);
    this.stars.circle(
      this.ring,
      this.ringA,
      this.ringB,
      still ? 0.6 : dizzy * 2.4,
      Math.min(1, dizzy / 0.4),
      still ? 0 : t
    );
  }

  private ground(at: Vector3) {
    return this.floorAt(at.x, at.z) ?? this.floor;
  }
}

const COUNT = 5;
const SIZE = 0.15; // metres across

/** Little cartoon stars, circling round your head, dazed. */
export class Stars {
  private readonly sprites: Sprite[] = [];

  constructor(scene: Scene) {
    const map = star();
    for (let n = 0; n < COUNT; n++) {
      const sprite = new Sprite(
        new SpriteMaterial({ map, depthTest: false, depthWrite: false, fog: false, toneMapped: false })
      );
      sprite.renderOrder = 10;
      sprite.visible = false;
      this.sprites.push(sprite);
      scene.add(sprite);
    }
  }

  /**
   * Round a ring, its middle and the two ways across it (as long as its
   * radius each), how far round they've gone (radians), how much they're
   * there (0 to 1: popping up), and the time (for their twinkling; 0, still).
   */
  circle(middle: Vector3, a: Vector3, b: Vector3, round: number, there: number, time: number) {
    this.sprites.forEach((sprite, n) => {
      const angle = round + (n * Math.PI * 2) / COUNT;
      sprite.position.copy(middle).addScaledVector(a, Math.cos(angle)).addScaledVector(b, Math.sin(angle));
      const twinkle = time ? 0.85 + 0.15 * Math.sin(time * 7 + n * 2.1) : 1;
      sprite.scale.setScalar(SIZE * pop(there) * twinkle);
      sprite.material.rotation = time ? Math.sin(time * 2 + n) * 0.5 : 0;
      sprite.visible = there > 0;
    });
  }

  hide() {
    for (const sprite of this.sprites) sprite.visible = false;
  }
}

// A star as a child draws one: five round-cornered points, golden, outlined
// in orange, with a shine on it and a soft glow round it.
function star() {
  const S = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = S;
  const g = canvas.getContext("2d")!;
  const glow = g.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
  glow.addColorStop(0, "rgba(255, 228, 120, 0.3)");
  glow.addColorStop(1, "rgba(255, 200, 60, 0)");
  g.fillStyle = glow;
  g.fillRect(0, 0, S, S);
  g.beginPath();
  for (let i = 0; i < 10; i++) {
    const r = i % 2 ? 24 : 56;
    const a = -Math.PI / 2 + (i * Math.PI) / 5;
    g.lineTo(S / 2 + r * Math.cos(a), S / 2 + 6 + r * Math.sin(a));
  }
  g.closePath();
  g.lineJoin = "round";
  g.lineWidth = 8;
  g.strokeStyle = "#d0700f";
  g.stroke();
  const fill = g.createLinearGradient(0, 20, 0, 110);
  fill.addColorStop(0, "#fff7b0");
  fill.addColorStop(1, "#ffc21f");
  g.fillStyle = fill;
  g.fill();
  g.fillStyle = "rgba(255, 255, 255, 0.85)";
  g.beginPath();
  g.ellipse(52, 50, 8, 4.5, -0.6, 0, Math.PI * 2);
  g.fill();
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

// Popping up: a little past full size, and back.
const pop = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u < 1 ? u * (1 + 0.6 * Math.sin(Math.PI * u)) : 1;
};

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
