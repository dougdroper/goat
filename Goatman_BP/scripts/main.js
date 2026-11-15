import { world, system } from "@minecraft/server";

// ============================ Settings you can tweak ============================
const GOATMAN = "goatman:goatman";

// Jump scares (random, per player)
const SCARE_MIN_MINUTES = 2;
const SCARE_MAX_MINUTES = 6;
const SCARE_SECONDS = 1.2; // how long the face stays on screen

// Stalking
const NOTICE_RANGE = 32; // he starts staring when you come this close
const STARE_SECONDS = 10; // how long he stares before attacking
const ATTACK_IF_CLOSER_THAN = 3; // walk right up to him and he attacks early
const GIVE_UP_RANGE = 80; // he gives up if you get this far away...
const GIVE_UP_SECONDS = 30; // ...for this long

// Night sounds (seconds between each, random within the range)
const FOOTSTEPS_EVERY = [45, 120];
const HELP_CALL_EVERY = [60, 180];
const I_SEE_YOU_EVERY = [150, 400];

// This secret title text tells the resource pack to show the face.
// MUST match the text in Goatman_RP/ui/hud_screen.json.
const SCARE_KEY = "§0§1§2§3§4§5";
// ================================================================================

const MODE = "goatman:mode";
const SEC = 20;
const stareInfo = new Map(); // goatman id -> { playerId, endTick }
const lostSince = new Map(); // goatman id -> tick the player was last nearby
const timers = new Map(); // player id -> { scare, steps, help, voice }

const rand = (min, max) => min + Math.random() * (max - min);
const randTicks = ([min, max]) => Math.floor(rand(min, max) * SEC);
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);

function safe(label, fn) {
  try {
    fn();
  } catch (e) {
    console.warn(`[Goatman] ${label}: ${e}`);
  }
}

function isSpectator(player) {
  try {
    return String(player.getGameMode()).toLowerCase() === "spectator";
  } catch {
    return false;
  }
}

function nearestPlayer(entity, maxDistance) {
  let best;
  let bestDist = maxDistance;
  for (const player of world.getAllPlayers()) {
    if (player.dimension.id !== entity.dimension.id || isSpectator(player)) continue;
    const d = dist(player.location, entity.location);
    if (d <= bestDist) {
      best = player;
      bestDist = d;
    }
  }
  return { player: best, distance: bestDist };
}

function playerById(id) {
  return world.getAllPlayers().find((p) => p.id === id);
}

function isNight() {
  const t = world.getTimeOfDay();
  return t >= 13000 && t <= 23000;
}

/** Play a sound at a spot so everyone nearby hears it coming from there. */
function playAt(dimension, sound, location, options = {}) {
  try {
    dimension.playSound(sound, location, options);
  } catch {
    for (const p of world.getAllPlayers()) {
      if (p.dimension.id === dimension.id) p.playSound(sound, { ...options, location });
    }
  }
}

// ================================ Goatman brain =================================
function startStare(goatman, player) {
  goatman.triggerEvent("goatman:stare");
  stareInfo.set(goatman.id, { playerId: player.id, endTick: system.currentTick + STARE_SECONDS * SEC });
  goatman.teleport(goatman.location, { facingLocation: player.getHeadLocation() });
  // He whispers to you as he locks eyes.
  system.runTimeout(() => safe("whisper", () => player.playSound("goatman.i_see_you")), 30);
}

function startHunt(goatman) {
  stareInfo.delete(goatman.id);
  lostSince.delete(goatman.id);
  goatman.triggerEvent("goatman:hunt");
  playAt(goatman.dimension, "goatman.roar", goatman.location, { volume: 4 });
}

function goRoam(goatman) {
  stareInfo.delete(goatman.id);
  lostSince.delete(goatman.id);
  goatman.triggerEvent("goatman:roam");
}

/** Twitchy, unpredictable movement while chasing: side-lunges and leaps. */
function moveErratically(goatman, player) {
  if (!goatman.isOnGround) return;
  const dx = player.location.x - goatman.location.x;
  const dz = player.location.z - goatman.location.z;
  const len = Math.hypot(dx, dz) || 1;
  const fx = dx / len;
  const fz = dz / len;
  const roll = Math.random();
  if (roll < 0.14) {
    // jerk sideways
    const side = Math.random() < 0.5 ? -1 : 1;
    goatman.applyImpulse({ x: -fz * side * 0.5 + fx * 0.1, y: 0.15, z: fx * side * 0.5 + fz * 0.1 });
  } else if (roll < 0.19 && len < 10) {
    // pounce
    goatman.applyImpulse({ x: fx * 0.9, y: 0.4, z: fz * 0.9 });
  }
}

function updateGoatman(goatman, now) {
  const mode = goatman.getProperty(MODE);

  if (mode === "roam") {
    const { player } = nearestPlayer(goatman, NOTICE_RANGE);
    if (player) startStare(goatman, player);
    return;
  }

  if (mode === "stare") {
    let info = stareInfo.get(goatman.id);
    let player = info && playerById(info.playerId);
    if (!player) {
      player = nearestPlayer(goatman, GIVE_UP_RANGE).player;
      if (!player) return goRoam(goatman);
      info = { playerId: player.id, endTick: now + STARE_SECONDS * SEC };
      stareInfo.set(goatman.id, info);
    }
    const d = dist(player.location, goatman.location);
    if (d > GIVE_UP_RANGE || player.dimension.id !== goatman.dimension.id) return goRoam(goatman);
    if (now >= info.endTick || d < ATTACK_IF_CLOSER_THAN) return startHunt(goatman);
    // Keep his whole body turned toward you. He doesn't blink.
    goatman.teleport(goatman.location, { facingLocation: player.getHeadLocation() });
    return;
  }

  if (mode === "chase") {
    const { player } = nearestPlayer(goatman, GIVE_UP_RANGE);
    if (player) {
      lostSince.set(goatman.id, now); // last time a player was in range
      moveErratically(goatman, player);
    } else if (!lostSince.has(goatman.id)) {
      lostSince.set(goatman.id, now);
    } else if (now - lostSince.get(goatman.id) > GIVE_UP_SECONDS * SEC) {
      goRoam(goatman);
    }
  }
}

// Hit him while he's staring or wandering and he attacks straight away.
world.afterEvents.entityHurt.subscribe((event) => {
  const goatman = event.hurtEntity;
  if (goatman?.typeId !== GOATMAN) return;
  if (event.damageSource.damagingEntity?.typeId !== "minecraft:player") return;
  safe("hurt", () => {
    if (goatman.getProperty(MODE) !== "chase") startHunt(goatman);
  });
});

// ================================== Jump scare ==================================
function isOpen(dimension, x, y, z) {
  try {
    const block = dimension.getBlock({ x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) });
    return block !== undefined && (block.isAir || block.isLiquid);
  } catch {
    return false;
  }
}

function findSpotInFront(player) {
  const view = player.getViewDirection();
  const flat = Math.hypot(view.x, view.z) || 1;
  const base = player.location;
  for (const d of [1.6, 1.2, 2.2, 0.9]) {
    const x = base.x + (view.x / flat) * d;
    const z = base.z + (view.z / flat) * d;
    if (isOpen(player.dimension, x, base.y, z) && isOpen(player.dimension, x, base.y + 1, z)) {
      return { x, y: base.y, z };
    }
  }
  return undefined;
}

function jumpScare(player) {
  const dimension = player.dimension;
  const spot = findSpotInFront(player);

  if (spot) {
    let goatman = dimension.getEntities({ type: GOATMAN, location: player.location, maxDistance: 64 })[0];
    if (!goatman) goatman = dimension.spawnEntity(GOATMAN, spot);
    goatman.teleport(spot, { facingLocation: player.getHeadLocation() });
    stareInfo.delete(goatman.id);
    goatman.triggerEvent("goatman:hunt"); // no staring this time — he's already here
  }

  player.playSound("goatman.jumpscare", { volume: 1.0, pitch: 1.0 });

  const ticks = Math.round(SCARE_SECONDS * SEC);
  player.onScreenDisplay.setTitle(SCARE_KEY, { fadeInDuration: 0, stayDuration: ticks, fadeOutDuration: 0 });
  system.runTimeout(() => {
    safe("clear title", () => {
      player.onScreenDisplay.setTitle("§r", { fadeInDuration: 0, stayDuration: 1, fadeOutDuration: 0 });
      player.onScreenDisplay.clearTitle();
    });
  }, ticks);

  player.addEffect("slowness", 40, { amplifier: 3, showParticles: false });
  player.addEffect("darkness", 200, { amplifier: 0, showParticles: false });
}

// ================================= Night sounds =================================
/** Someone sprints past you in the dark — or runs straight up behind you and stops. */
function runningFootsteps(player) {
  const p = player.location;
  const steps = 16;
  let path;

  if (Math.random() < 0.35) {
    // Runs up behind you... then silence.
    const view = player.getViewDirection();
    const flat = Math.hypot(view.x, view.z) || 1;
    const bx = -view.x / flat;
    const bz = -view.z / flat;
    path = (i) => {
      const d = 22 - (i / (steps - 1)) * 19.5; // from 22 blocks away to 2.5 blocks behind you
      return { x: p.x + bx * d, y: p.y, z: p.z + bz * d };
    };
  } else {
    // Runs past you, somewhere out of sight.
    const angle = Math.random() * Math.PI * 2;
    const off = rand(9, 15);
    const cx = p.x + Math.cos(angle) * off;
    const cz = p.z + Math.sin(angle) * off;
    const tx = -Math.sin(angle);
    const tz = Math.cos(angle);
    path = (i) => {
      const s = (i - steps / 2) * 1.6;
      return { x: cx + tx * s, y: p.y, z: cz + tz * s };
    };
  }

  for (let i = 0; i < steps; i++) {
    system.runTimeout(() => {
      safe("footstep", () => {
        const sound = i % 2 === 0 ? "step.grass" : "step.gravel";
        player.playSound(sound, { location: path(i), volume: 1.0, pitch: rand(0.75, 0.95) });
      });
    }, i * 4);
  }
}

/** A distant voice calls for help. If the Goatman is nearby, it comes from him. */
function distantHelp(player) {
  const p = player.location;
  const goatman = player.dimension.getEntities({ type: GOATMAN, location: p, maxDistance: 64 })[0];
  let location;
  if (goatman) {
    location = goatman.location;
  } else {
    const angle = Math.random() * Math.PI * 2;
    const d = rand(24, 36);
    location = { x: p.x + Math.cos(angle) * d, y: p.y + 2, z: p.z + Math.sin(angle) * d };
  }
  player.playSound("goatman.help", { location, volume: 3.0 });
}

function updateNightSounds(player, now) {
  let t = timers.get(player.id);
  if (!t) {
    t = {
      scare: now + randTicks([SCARE_MIN_MINUTES * 60, SCARE_MAX_MINUTES * 60]),
      steps: now + randTicks(FOOTSTEPS_EVERY),
      help: now + randTicks(HELP_CALL_EVERY),
      voice: now + randTicks(I_SEE_YOU_EVERY),
    };
    timers.set(player.id, t);
    return;
  }

  if (now >= t.scare) {
    t.scare = now + randTicks([SCARE_MIN_MINUTES * 60, SCARE_MAX_MINUTES * 60]);
    safe("jump scare", () => jumpScare(player));
  }

  const night = isNight() && player.dimension.id === "minecraft:overworld";
  if (now >= t.steps) {
    t.steps = now + randTicks(FOOTSTEPS_EVERY);
    if (night) safe("footsteps", () => runningFootsteps(player));
  }
  if (now >= t.help) {
    t.help = now + randTicks(HELP_CALL_EVERY);
    if (night) safe("help", () => distantHelp(player));
  }
  if (now >= t.voice) {
    t.voice = now + randTicks(I_SEE_YOU_EVERY);
    if (night) safe("voice", () => player.playSound("goatman.i_see_you"));
  }
}

// =================================== Main loop ==================================
system.runInterval(() => {
  const now = system.currentTick;

  for (const dimId of ["overworld", "nether", "the_end"]) {
    let goatmen = [];
    try {
      goatmen = world.getDimension(dimId).getEntities({ type: GOATMAN });
    } catch {
      continue;
    }
    for (const goatman of goatmen) safe("update", () => updateGoatman(goatman, now));
  }

  if (now % SEC < 5) {
    for (const player of world.getAllPlayers()) safe("night", () => updateNightSounds(player, now));
  }
}, 5);

// ================================ Test commands =================================
//   /scriptevent goatman:scare      jump scare now
//   /scriptevent goatman:footsteps  running footsteps
//   /scriptevent goatman:help       distant cry for help
//   /scriptevent goatman:voice      "I see you"
system.afterEvents.scriptEventReceive.subscribe((event) => {
  const actions = {
    "goatman:scare": jumpScare,
    "goatman:footsteps": runningFootsteps,
    "goatman:help": distantHelp,
    "goatman:voice": (p) => p.playSound("goatman.i_see_you"),
  };
  const action = actions[event.id];
  if (!action) return;
  const targets = event.sourceEntity?.typeId === "minecraft:player" ? [event.sourceEntity] : world.getAllPlayers();
  for (const player of targets) safe(event.id, () => action(player));
});
