import { world, system } from "@minecraft/server";

// ---------------- Settings you can tweak ----------------
const GOATMAN = "goatman:goatman";
const MIN_MINUTES = 2; // shortest time between jump scares
const MAX_MINUTES = 6; // longest time between jump scares
const SCARE_SECONDS = 1.2; // how long the scary face stays on screen
// This secret title text tells the resource pack to show the face.
// It's made only of colour codes so nothing readable appears on screen.
// MUST match the text in Goatman_RP/ui/hud_screen.json.
const SCARE_KEY = "§0§1§2§3§4§5";
// --------------------------------------------------------

const TICKS_PER_MINUTE = 20 * 60;
const nextScareTick = new Map();

function randomDelay() {
  const min = MIN_MINUTES * TICKS_PER_MINUTE;
  const max = MAX_MINUTES * TICKS_PER_MINUTE;
  return min + Math.floor(Math.random() * (max - min));
}

function isOpen(dimension, x, y, z) {
  try {
    const block = dimension.getBlock({ x: Math.floor(x), y: Math.floor(y), z: Math.floor(z) });
    return block !== undefined && (block.isAir || block.isLiquid);
  } catch {
    return false;
  }
}

// Find a spot right in front of the player's face with room for the Goatman to stand.
function findSpotInFront(player) {
  const view = player.getViewDirection();
  const flat = Math.hypot(view.x, view.z) || 1;
  const fx = view.x / flat;
  const fz = view.z / flat;
  const base = player.location;

  for (const dist of [1.6, 1.2, 2.2, 0.9]) {
    const x = base.x + fx * dist;
    const z = base.z + fz * dist;
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
    // Reuse a nearby Goatman if there is one, otherwise summon a new one.
    let goatman = dimension.getEntities({ type: GOATMAN, location: player.location, maxDistance: 64 })[0];
    if (!goatman) goatman = dimension.spawnEntity(GOATMAN, spot);
    goatman.teleport(spot, { facingLocation: player.getHeadLocation() });
  }

  // The scream (only this player hears it, at full volume).
  player.playSound("goatman.jumpscare", { volume: 1.0, pitch: 1.0 });

  // Flash the full-screen face (drawn by Goatman_RP/ui/hud_screen.json).
  const ticks = Math.round(SCARE_SECONDS * 20);
  player.onScreenDisplay.setTitle(SCARE_KEY, { fadeInDuration: 0, stayDuration: ticks, fadeOutDuration: 0 });
  system.runTimeout(() => {
    try {
      player.onScreenDisplay.setTitle("§r", { fadeInDuration: 0, stayDuration: 1, fadeOutDuration: 0 });
      player.onScreenDisplay.clearTitle();
    } catch {
      // player left the game
    }
  }, ticks);

  // Freeze them for a moment and plunge them into darkness.
  player.addEffect("slowness", 40, { amplifier: 3, showParticles: false });
  player.addEffect("darkness", 200, { amplifier: 0, showParticles: false });
}

// Check every second whether it's time to scare someone.
system.runInterval(() => {
  const now = system.currentTick;
  for (const player of world.getAllPlayers()) {
    if (!nextScareTick.has(player.id)) {
      nextScareTick.set(player.id, now + randomDelay());
      continue;
    }
    if (now >= nextScareTick.get(player.id)) {
      nextScareTick.set(player.id, now + randomDelay());
      try {
        jumpScare(player);
      } catch (e) {
        console.warn(`[Goatman] jump scare failed: ${e}`);
      }
    }
  }
}, 20);

// Test it any time with the command:   /scriptevent goatman:scare
system.afterEvents.scriptEventReceive.subscribe((event) => {
  if (event.id !== "goatman:scare") return;
  const target = event.sourceEntity?.typeId === "minecraft:player" ? [event.sourceEntity] : world.getAllPlayers();
  for (const player of target) {
    try {
      jumpScare(player);
    } catch (e) {
      console.warn(`[Goatman] jump scare failed: ${e}`);
    }
  }
});
