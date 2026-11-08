"use client";

import { useEffect, useRef, useState } from "react";
import type * as ThreeNS from "three";

type Props = {
  className?: string;
  /** Read out by screen readers in place of the canvas. */
  label?: string;
  /** Show the small "Drag to turn it" hint under the model. */
  hint?: boolean;
};

/** Colours sampled from photos of the real device. */
const IVORY = "#E6DFCF"; // the sparkly white 3D-printed filament
const GROOVE = "#C4BBA9"; // the fine shadow lines between parts
const HOLLOW = "#6F6658"; // inside the vents
const PLUG = "#EEE7D8"; // the USB-C plug and cable
const DISPLAY_BG = "#0E0F30";
const SCREEN_CYAN = "#2DE6D2";

/**
 * Nemo in 3D, modelled in code from photos of the finished device: a 61 x 113 x 32 mm sparkly ivory box,
 * with two mic holes, a camera and a small screen on the front, a USB-C cable out of the top,
 * vents and a button on the sides, and a clip on the back.
 * three.js is loaded only in the browser, only when this component mounts.
 * It sways gently on its own (not under reduced motion) and can be dragged sideways to turn it.
 * Vertical swipes still scroll the page on touch screens.
 */
export function DeviceModel({
  className,
  label = "Nemo, a small white device about the size of a deck of cards, with a round black camera in the middle, a small screen below it showing a pair of glowing eyes, a button on its side and a USB cable coming out of the top, shown in 3D.",
  hint = false,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    let disposed = false;
    let teardown = () => {};

    (async () => {
      const THREE = await import("three");
      const { RoomEnvironment } = await import("three/examples/jsm/environments/RoomEnvironment.js");
      const { toCreasedNormals } = await import("three/examples/jsm/utils/BufferGeometryUtils.js");
      if (disposed) return;

      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      } catch {
        setStatus("error");
        return;
      }
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.toneMapping = THREE.NeutralToneMapping;
      renderer.toneMappingExposure = 1;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFShadowMap;
      const canvas = renderer.domElement;
      canvas.setAttribute("aria-hidden", "true");
      canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;touch-action:pan-y;cursor:grab;" +
        // The cable runs up and out of the picture, so fade the top edge.
        "-webkit-mask-image:linear-gradient(to bottom,transparent,#000 14%);mask-image:linear-gradient(to bottom,transparent,#000 14%);";
      wrap.appendChild(canvas);

      const scene = new THREE.Scene();
      const pmrem = new THREE.PMREMGenerator(renderer);
      const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environment = envTex;
      scene.environmentIntensity = 0.55;

      const camera = new THREE.PerspectiveCamera(28, 1, 1, 2000);

      const key = new THREE.DirectionalLight(0xffffff, 1.5);
      key.position.set(-70, 240, 170);
      key.castShadow = true;
      key.shadow.mapSize.set(1024, 1024);
      key.shadow.radius = 6;
      key.shadow.bias = -0.0005;
      Object.assign(key.shadow.camera, { near: 10, far: 600, left: -120, right: 120, top: 120, bottom: -120 });
      scene.add(key);

      // A soft light from the viewer's side keeps the front a clean white, while the sides fall into gentle shade.
      const fill = new THREE.DirectionalLight(0xffffff, 1);
      fill.position.set(10, 60, 300);
      scene.add(fill);

      // Turntable: `spin` turns around the vertical axis, `model` holds the device.
      const spin = new THREE.Group();
      scene.add(spin);

      const ground = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), new THREE.ShadowMaterial({ opacity: 0.16 }));
      ground.rotation.x = -Math.PI / 2;
      ground.receiveShadow = true;
      scene.add(ground);

      let height = 120;
      let radiusXZ = 40;

      const fit = () => {
        const w = wrap.clientWidth || 1;
        const h = wrap.clientHeight || 1;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
        const distH = (height / 2) / tanV;
        const distW = radiusXZ / (tanV * camera.aspect);
        const dist = Math.max(distH, distW) * 1.06 + radiusXZ;
        const target = new THREE.Vector3(0, height * 0.5, 0);
        camera.position.set(0, height * 0.5 + dist * 0.18, dist);
        camera.lookAt(target);
        camera.updateProjectionMatrix();
      };

      const { model, cable } = buildDevice(THREE, toCreasedNormals);

      // Centre it on the turntable and stand it on the ground.
      const box = new THREE.Box3().setFromObject(model);
      const size = box.getSize(new THREE.Vector3());
      const centre = box.getCenter(new THREE.Vector3());
      model.position.set(-centre.x, -box.min.y, -centre.z);
      model.add(cable); // added after measuring, so the framing is based on the device alone
      spin.add(model);
      height = size.y;
      radiusXZ = Math.hypot(size.x, size.z) / 2;
      fit();

      // ----- Interaction: drag sideways to turn, with a little inertia -----
      const REST = -0.45; // a three-quarter view of the front
      let angle = REST;
      let velocity = 0;
      let dragging = false;
      let lastX = 0;
      let lastMove = 0;

      const onDown = (e: PointerEvent) => {
        dragging = true;
        lastX = e.clientX;
        velocity = 0;
        canvas.style.cursor = "grabbing";
      };
      const onMove = (e: PointerEvent) => {
        if (!dragging) return;
        const dx = e.clientX - lastX;
        lastX = e.clientX;
        const delta = dx * 0.012;
        angle += delta;
        velocity = delta;
        lastMove = performance.now();
      };
      const onUp = () => {
        dragging = false;
        canvas.style.cursor = "grab";
      };
      canvas.addEventListener("pointerdown", onDown);
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);

      // ----- Render loop, paused while off screen -----
      let visible = true;
      let frame = 0;
      const clock = new THREE.Clock();
      let swayTime = 0;

      const tick = () => {
        frame = 0;
        const dt = Math.min(clock.getDelta(), 0.05);
        if (!dragging) {
          angle += velocity;
          velocity *= 0.92;
          if (!reduce) {
            swayTime += dt;
            // After a drag, settle for a moment before swaying again.
            const idle = performance.now() - lastMove > 1500 ? 1 : 0;
            angle += Math.cos(swayTime * 0.6) * 0.0035 * idle;
          }
        }
        spin.rotation.y = angle;
        renderer.render(scene, camera);
        if (visible) frame = requestAnimationFrame(tick);
      };

      const io = new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        if (visible && !frame) {
          clock.getDelta();
          frame = requestAnimationFrame(tick);
        }
      });
      io.observe(wrap);

      const ro = new ResizeObserver(() => {
        fit();
        renderer.render(scene, camera);
      });
      ro.observe(wrap);

      setStatus("ready");
      frame = requestAnimationFrame(tick);

      teardown = () => {
        cancelAnimationFrame(frame);
        io.disconnect();
        ro.disconnect();
        canvas.removeEventListener("pointerdown", onDown);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onUp);
        model.traverse((o) => {
          const mesh = o as InstanceType<typeof THREE.Mesh>;
          if (!mesh.isMesh) return;
          mesh.geometry.dispose();
          const mat = mesh.material as InstanceType<typeof THREE.MeshStandardMaterial>;
          mat.map?.dispose();
          mat.normalMap?.dispose();
          mat.emissiveMap?.dispose();
          mat.dispose();
        });
        ground.geometry.dispose();
        (ground.material as InstanceType<typeof THREE.Material>).dispose();
        envTex.dispose();
        pmrem.dispose();
        renderer.dispose();
        canvas.remove();
      };
    })().catch(() => {
      if (!disposed) setStatus("error");
    });

    return () => {
      disposed = true;
      teardown();
    };
  }, []);

  return (
    <div className={`flex flex-col ${className ?? ""}`}>
      <div ref={wrapRef} role="img" aria-label={label} className="relative min-h-0 w-full flex-1">
        {status === "loading" && (
          <div aria-hidden="true" className="absolute inset-0 grid place-items-center">
            <span className="h-24 w-16 animate-pulse rounded-[1.25rem] bg-navy/10" />
          </div>
        )}
        {status === "error" && (
          <p className="absolute inset-0 grid place-items-center px-6 text-center text-base text-navy">
            The 3D view couldn&rsquo;t load on this browser.
          </p>
        )}
      </div>
      {hint && status === "ready" && (
        <p className="mt-2 text-center text-base text-navy/80">Drag to turn it around</p>
      )}
    </div>
  );
}

type Three = typeof ThreeNS;
type Creased = (geo: ThreeNS.BufferGeometry, angle?: number) => ThreeNS.BufferGeometry;

/** A rounded rectangle centred on the origin, for extruding. */
function roundedRect(THREE: Three, w: number, h: number, r: number) {
  const x = -w / 2;
  const y = -h / 2;
  const shape = new THREE.Shape();
  shape.moveTo(x + r, y);
  shape.lineTo(x + w - r, y);
  shape.quadraticCurveTo(x + w, y, x + w, y + r);
  shape.lineTo(x + w, y + h - r);
  shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  shape.lineTo(x + r, y + h);
  shape.quadraticCurveTo(x, y + h, x, y + h - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  return shape;
}

/** A rounded rectangular cut-out, for the `holes` of a shape. */
function rectHole(THREE: Three, w: number, h: number, r: number, cx = 0, cy = 0) {
  const pts = roundedRect(THREE, w, h, r).getPoints(10);
  return new THREE.Path(pts.map((p) => new THREE.Vector2(p.x + cx, p.y + cy)).reverse());
}

function circlePath(THREE: Three, x: number, y: number, r: number) {
  const path = new THREE.Path();
  path.absarc(x, y, r, 0, Math.PI * 2, true);
  return path;
}

/** Extrudes a shape into a slab with a small rounded edge, centred on z = 0. */
function slab(THREE: Three, shape: ThreeNS.Shape, depth: number, bevel: number) {
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: depth - bevel * 2,
    bevelEnabled: true,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelOffset: -bevel,
    bevelSegments: 6,
    curveSegments: 24,
  });
  geo.translate(0, 0, -(depth - bevel * 2) / 2);
  return geo;
}

/** A flat, sharp-edged plate, centred on z = 0. Used for the faces, so small holes stay crisp. */
function flat(THREE: Three, shape: ThreeNS.Shape, depth: number) {
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 24 });
  geo.translate(0, 0, -depth / 2);
  return geo;
}

/** The sloped frame around the screen: four faces running from the outer opening down to the display. */
function chamfer(THREE: Three, ow: number, oh: number, iw: number, ih: number, depth: number) {
  const [ox, oy, ix, iy] = [ow / 2, oh / 2, iw / 2, ih / 2];
  const z = -depth;
  const quad = (a: number[], b: number[], c: number[], d: number[]) => [...a, ...b, ...c, ...a, ...c, ...d];
  const positions = [
    ...quad([-ox, oy, 0], [ox, oy, 0], [ix, iy, z], [-ix, iy, z]),
    ...quad([ox, oy, 0], [ox, -oy, 0], [ix, -iy, z], [ix, iy, z]),
    ...quad([ox, -oy, 0], [-ox, -oy, 0], [-ix, -iy, z], [ix, -iy, z]),
    ...quad([-ox, -oy, 0], [-ox, oy, 0], [-ix, iy, z], [-ix, -iy, z]),
  ];
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();
  return geo;
}

/** The sparkly 3D-printed filament: warm ivory with fine glints that catch the light as it turns. */
function speckle(THREE: Three) {
  const SIZE = 1024;
  const TILE_MM = 48;
  const PX = SIZE / TILE_MM;
  const canvases = [0, 1, 2].map(() => {
    const c = document.createElement("canvas");
    c.width = c.height = SIZE;
    return c;
  });
  const [cColor, cGlint, cNormal] = canvases;
  const color = cColor.getContext("2d");
  const glint = cGlint.getContext("2d");
  const normal = cNormal.getContext("2d");
  if (color && glint && normal) {
    color.fillStyle = IVORY;
    color.fillRect(0, 0, SIZE, SIZE);
    glint.fillStyle = "#000";
    glint.fillRect(0, 0, SIZE, SIZE);
    normal.fillStyle = "rgb(128,128,255)";
    normal.fillRect(0, 0, SIZE, SIZE);

    // Seeded, so the sparkle looks the same on every visit.
    let seed = 20261108;
    const rand = () => {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const dot = (g: CanvasRenderingContext2D, x: number, y: number, r: number) => {
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    };

    for (let i = 0; i < 1700; i++) {
      const x = rand() * SIZE;
      const y = rand() * SIZE;
      const r = (0.07 + rand() * rand() * 0.17) * PX;
      const a = rand() * Math.PI * 2;
      const tilt = 0.25 + rand() * 0.6;
      color.fillStyle = "#FFFFFF";
      dot(color, x, y, r);
      const v = Math.round(90 + rand() * 165);
      glint.fillStyle = `rgb(${v},${v},${v})`;
      dot(glint, x, y, r);
      normal.fillStyle = `rgb(${Math.round((Math.cos(a) * tilt + 1) * 127.5)},${Math.round((Math.sin(a) * tilt + 1) * 127.5)},${Math.round(Math.sqrt(1 - tilt * tilt) * 255)})`;
      dot(normal, x, y, r);
    }
  }
  const [map, emissiveMap, normalMap] = canvases.map((c) => {
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(1 / TILE_MM, 1 / TILE_MM); // the extruded parts have UVs in millimetres
    tex.anisotropy = 8;
    return tex;
  });
  map.colorSpace = THREE.SRGBColorSpace;
  emissiveMap.colorSpace = THREE.SRGBColorSpace;
  return { map, emissiveMap, normalMap };
}

/** What the screen shows, traced from the real display: two cyan domes and a small mouth on deep navy. */
function drawScreen(THREE: Three) {
  const W = 880;
  const H = 484;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d");
  if (g) {
    const bg = g.createRadialGradient(W * 0.5, H * 0.5, 40, W * 0.5, H * 0.5, W * 0.62);
    bg.addColorStop(0, "#1C1D52");
    bg.addColorStop(1, DISPLAY_BG);
    g.fillStyle = bg;
    g.fillRect(0, 0, W, H);

    g.shadowColor = "rgba(45,230,210,0.75)";
    g.shadowBlur = 34;
    g.fillStyle = SCREEN_CYAN;
    const baseY = H * 0.435;
    for (const cx of [W * 0.336, W * 0.648]) {
      g.beginPath();
      g.ellipse(cx, baseY, W * 0.108, H * 0.24, 0, Math.PI, 0);
      g.closePath();
      g.fill();
    }
    g.shadowBlur = 20;
    g.beginPath();
    g.roundRect(W * 0.648 - W * 0.055, H * 0.625, W * 0.11, H * 0.052, H * 0.026);
    g.fill();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  return tex;
}

/** The printed ribs of the strip below the clip on the back. */
function drawRibs(THREE: Three) {
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 16;
  const g = c.getContext("2d");
  if (g) {
    g.fillStyle = "#FFFFFF";
    g.fillRect(0, 0, 64, 16);
    g.fillStyle = "#8F8A80";
    g.fillRect(0, 0, 64, 5);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 80);
  tex.anisotropy = 8;
  return tex;
}

/**
 * Builds the finished device, front facing +z, in millimetres, from photos of the real thing.
 * Front, top to bottom: two mic holes (upper right), camera, screen. USB-C cable out of the top.
 * Back: a clip, a ribbed strip below it, two small holes and two eyelets at the bottom edge.
 * Each side: two square snap-fit panels and a 2 x 2 vent. The button is on the right side.
 * `model` is the device itself; `cable` is kept apart so it doesn't count towards framing.
 */
function buildDevice(THREE: Three, creased: Creased) {
  const model = new THREE.Group();
  const add = (geo: ThreeNS.BufferGeometry, mat: ThreeNS.Material, x = 0, y = 0, z = 0, parent: ThreeNS.Group = model) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    parent.add(m);
    return m;
  };
  const smooth = (geo: ThreeNS.BufferGeometry) => {
    const out = creased(geo, 0.7);
    geo.dispose();
    return out;
  };

  const matte = (hex: string, extra: Partial<ThreeNS.MeshPhysicalMaterialParameters> = {}) =>
    new THREE.MeshPhysicalMaterial({ color: new THREE.Color(hex), roughness: 0.68, ...extra });
  const glossBlack = (hex: string, roughness: number) => new THREE.MeshPhysicalMaterial({ color: hex, roughness, clearcoat: 1, clearcoatRoughness: 0.08 });

  const { map, emissiveMap, normalMap } = speckle(THREE);
  const ivory = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    map,
    normalMap,
    normalScale: new THREE.Vector2(0.25, 0.25),
    emissive: 0xffffff,
    emissiveMap,
    emissiveIntensity: 0.3,
    roughness: 0.62,
  });
  const ivoryPlain = matte(IVORY);
  const shadowLine = matte(GROOVE);
  const hollow = matte(HOLLOW, { roughness: 0.9 });

  // Overall size: 61 x 113 mm, about 32 mm deep. A main shell and a thin back plate.
  const W = 61;
  const H = 113;
  const CORNER = 3.2;
  const EDGE = 0.8;
  const SHELL_D = 28.4;
  const SEAM_GAP = 0.3;
  const PLATE_D = 2.9;
  const DEPTH = SHELL_D + SEAM_GAP + PLATE_D;
  const FRONT = DEPTH / 2;
  const BACK = -DEPTH / 2;
  const FACE_D = 2;
  /** z position from a fraction of the depth, measured from the front. */
  const zAt = (f: number) => FRONT - f * DEPTH;

  // Front features, measured from the photos (origin at the centre of the front).
  const SCREEN = { x: 0, y: -40, outerW: 26, outerH: 15, w: 22, h: 12.1, sink: 1.4 };
  const CAM = { x: 0, y: 11.3 };
  const MIC_FRONT = [
    { x: 16.5, y: 31.9, r: 0.75 },
    { x: 14, y: 28.3, r: 0.75 },
  ];
  // Back features.
  const MIC_BACK = [
    { x: 16.6, y: 33.4, r: 0.65, glow: "#E8452E" },
    { x: 16.6, y: 28.4, r: 1.15, glow: "#D9674E" },
  ];
  const CLIP = { w: 16.6, top: H / 2 + 2.5, bottom: 2, thick: 3, gap: 2 };
  const STRIP = { w: 10.5, top: 8, bottom: -48.9 };

  /** A shell with rounded outer edges and a separate flat face, so openings in the face stay crisp. */
  const shellWithFace = (depth: number, centreZ: number, faceZ: number, bevel: number, holes: ThreeNS.Path[]) => {
    const ring = roundedRect(THREE, W, H, CORNER);
    ring.holes.push(rectHole(THREE, W - 8, H - 8, 2));
    add(smooth(slab(THREE, ring, depth, bevel)), ivory, 0, 0, centreZ);
    const face = roundedRect(THREE, W - bevel * 2 + 0.02, H - bevel * 2 + 0.02, Math.max(CORNER - bevel, 0.2));
    face.holes.push(...holes);
    add(flat(THREE, face, FACE_D), ivory, 0, 0, faceZ);
  };

  // Main shell
  shellWithFace(SHELL_D, FRONT - SHELL_D / 2, FRONT - FACE_D / 2 + 0.01, EDGE, [
    rectHole(THREE, SCREEN.outerW, SCREEN.outerH, 0.3, SCREEN.x, SCREEN.y),
    ...MIC_FRONT.map((m) => circlePath(THREE, m.x, m.y, m.r)),
  ]);

  // Back plate
  shellWithFace(PLATE_D, BACK + PLATE_D / 2, BACK + FACE_D / 2 - 0.01, 0.5, [
    rectHole(THREE, STRIP.w, STRIP.top - STRIP.bottom, 0.3, 0, (STRIP.top + STRIP.bottom) / 2),
    ...MIC_BACK.map((m) => circlePath(THREE, m.x, m.y, m.r)),
  ]);

  // The fine line where the back plate meets the shell
  add(flat(THREE, roundedRect(THREE, W - 1.2, H - 1.2, CORNER - 0.6), SEAM_GAP + 2), shadowLine, 0, 0, FRONT - SHELL_D - SEAM_GAP / 2);

  // Screen: a sloped frame sunk into the face, then the display at the bottom of it
  const frame = add(
    chamfer(THREE, SCREEN.outerW, SCREEN.outerH, SCREEN.w, SCREEN.h, SCREEN.sink),
    matte(IVORY, { side: THREE.DoubleSide }),
    SCREEN.x,
    SCREEN.y,
    FRONT,
  );
  frame.castShadow = false;
  const display = add(
    new THREE.PlaneGeometry(SCREEN.w, SCREEN.h),
    new THREE.MeshBasicMaterial({ map: drawScreen(THREE), toneMapped: false }),
    SCREEN.x,
    SCREEN.y,
    FRONT - SCREEN.sink,
  );
  display.castShadow = false;
  const glass = add(
    new THREE.PlaneGeometry(SCREEN.w, SCREEN.h),
    new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.05, roughness: 0.08, clearcoat: 1 }),
    SCREEN.x,
    SCREEN.y,
    FRONT - SCREEN.sink + 0.05,
  );
  glass.castShadow = false;

  // Camera: a soft, glossy black module with concentric rings around the lens
  const ringProfile = [
    [4.95, 0],
    [4.95, 0.3],
    [4.7, 0.62],
    [4.2, 0.8],
    [3.65, 0.72],
    [3.25, 0.34],
    [3.1, 0.1],
    [0, 0.1],
  ].map(([r, z]) => new THREE.Vector2(r, z));
  const camBody = add(new THREE.LatheGeometry(ringProfile, 72), glossBlack("#101114", 0.28), CAM.x, CAM.y, FRONT);
  camBody.rotation.x = Math.PI / 2;
  const rings: [number, number, string][] = [
    [2.75, 0.14, "#26282D"],
    [1.75, 0.1, "#2B2E34"],
    [0.95, 0.08, "#33373E"],
  ];
  for (const [r, tube, hex] of rings) {
    const ring = add(new THREE.TorusGeometry(r, tube, 12, 56), glossBlack(hex, 0.3), CAM.x, CAM.y, FRONT + 0.22);
    ring.castShadow = false;
  }
  const lens = add(
    new THREE.SphereGeometry(3, 48, 20, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshPhysicalMaterial({ color: "#07080B", roughness: 0.04, clearcoat: 1, clearcoatRoughness: 0.03, transparent: true, opacity: 0.82 }),
    CAM.x,
    CAM.y,
    FRONT + 0.1,
  );
  lens.rotation.x = Math.PI / 2;
  lens.scale.set(1, 0.2, 1);
  lens.castShadow = false;

  // Mic holes on the front
  for (const m of MIC_FRONT) add(new THREE.CircleGeometry(m.r + 0.3, 20), matte("#08080A"), m.x, m.y, FRONT - 0.45);

  // The two small holes on the back, with the red status light showing through
  for (const m of MIC_BACK) {
    const disc = add(new THREE.CircleGeometry(m.r + 0.3, 24), new THREE.MeshBasicMaterial({ color: m.glow, toneMapped: false }), m.x, m.y, BACK + 0.45);
    disc.rotation.y = Math.PI;
    disc.castShadow = false;
  }

  // Details on both sides: two square snap-fit panels and a 2 x 2 vent near the back
  const panelZ = zAt(0.24);
  for (const side of [1, -1]) {
    const onSide = (geo: ThreeNS.BufferGeometry, mat: ThreeNS.Material, y: number, z: number, proud: number) => {
      const m = add(geo, mat, side * (W / 2 + proud), y, z);
      m.rotation.y = (side * Math.PI) / 2;
      m.castShadow = false;
      return m;
    };
    for (const y of [40, -45]) {
      onSide(new THREE.PlaneGeometry(7.5, 7.5), shadowLine, y, panelZ, 0.02);
      onSide(new THREE.BoxGeometry(6.8, 6.8, 0.2), ivoryPlain, y, panelZ, 0.02);
    }
    for (const zo of [-1.75, 1.75]) {
      for (const yo of [-3.1, 3.1]) {
        onSide(new THREE.PlaneGeometry(1.9, 4.8), hollow, 6.8 + yo, zAt(0.79) + zo, 0.02);
      }
    }
  }

  // The one button: a small square block standing out of the right side
  const BUTTON = { y: 26.7, z: zAt(0.55), along: 7.4, tall: 5.6, out: 3.4 };
  const buttonSeat = add(new THREE.PlaneGeometry(BUTTON.along + 0.8, BUTTON.tall + 0.8), shadowLine, W / 2 + 0.03, BUTTON.y, BUTTON.z);
  buttonSeat.rotation.y = Math.PI / 2;
  buttonSeat.castShadow = false;
  const button = add(
    smooth(slab(THREE, roundedRect(THREE, BUTTON.along, BUTTON.tall, 0.7), BUTTON.out + 2, 0.45)),
    matte("#F7F4EE", { roughness: 0.55 }),
    W / 2 + BUTTON.out / 2 - 1,
    BUTTON.y,
    BUTTON.z,
  );
  button.rotation.y = Math.PI / 2;

  // The clip on the back: a flat bar held away from the body, joined at the top
  const clipH = CLIP.top - CLIP.bottom;
  const clipY = (CLIP.top + CLIP.bottom) / 2;
  add(smooth(slab(THREE, roundedRect(THREE, CLIP.w, clipH, 1), CLIP.thick, 0.5)), ivoryPlain, 0, clipY, BACK - CLIP.gap - CLIP.thick / 2);
  add(new THREE.BoxGeometry(CLIP.w - 1, 8, CLIP.gap + 1), ivoryPlain, 0, CLIP.top - 5, BACK - CLIP.gap / 2 + 0.5);

  // The ribbed strip below the clip, set into the back plate
  const stripH = STRIP.top - STRIP.bottom;
  const ribs = drawRibs(THREE);
  const strip = add(
    new THREE.PlaneGeometry(STRIP.w, stripH),
    new THREE.MeshPhysicalMaterial({ color: "#F4F0E7", map: ribs, roughness: 0.5 }),
    0,
    (STRIP.top + STRIP.bottom) / 2,
    BACK + 1.2,
  );
  strip.rotation.y = Math.PI;
  strip.castShadow = false;

  // Two small eyelets at the bottom edge, part of the back plate
  for (const x of [-24.3, 24.3]) {
    const tab = new THREE.Shape();
    tab.moveTo(-3, 2);
    tab.lineTo(-3, -2.9);
    tab.absarc(0, -2.9, 3, Math.PI, Math.PI * 2, false);
    tab.lineTo(3, 2);
    tab.closePath();
    tab.holes.push(circlePath(THREE, 0, -2.9, 1.45));
    add(smooth(slab(THREE, tab, PLATE_D, 0.3)), ivory, x, -H / 2, BACK + PLATE_D / 2);
  }

  // USB-C plug on the top edge
  const USB = { x: -6.6, z: 2 };
  const top = H / 2;
  const plug = matte(PLUG, { roughness: 0.5 });
  const upright = (geo: ThreeNS.BufferGeometry, mat: ThreeNS.Material, y: number, parent: ThreeNS.Group = model) => {
    const m = add(geo, mat, USB.x, y, USB.z, parent);
    m.rotation.x = -Math.PI / 2;
    return m;
  };
  upright(smooth(slab(THREE, roundedRect(THREE, 10.8, 7.2, 3.3), 6, 0.5)), plug, top + 3);
  upright(smooth(slab(THREE, roundedRect(THREE, 8, 5.6, 2.6), 5, 0.5)), plug, top + 8.2);
  for (let i = 0; i < 4; i++) {
    const grip = add(new THREE.BoxGeometry(5.6 - i * 0.5, 0.22, 0.12), matte("#BDB5A3"), USB.x, top + 1.5 + i * 1.05, USB.z + 3.6);
    grip.castShadow = false;
  }
  const relief = add(new THREE.CylinderGeometry(1.9, 2.4, 4.4, 28), plug, USB.x, top + 12.6, USB.z);
  relief.castShadow = true;

  // The cable, heading up and out of the picture
  const cable = new THREE.Group();
  const path = new THREE.CatmullRomCurve3(
    [
      [0, top + 13, 0],
      [-0.4, top + 30, -1],
      [-3, top + 55, -3],
      [-11, top + 82, -6],
      [-26, top + 110, -10],
      [-46, top + 134, -14],
    ].map(([x, y, z]) => new THREE.Vector3(USB.x + x, y, USB.z + z)),
  );
  add(new THREE.TubeGeometry(path, 90, 1.65, 14), matte(PLUG, { roughness: 0.45 }), 0, 0, 0, cable);

  return { model, cable };
}
