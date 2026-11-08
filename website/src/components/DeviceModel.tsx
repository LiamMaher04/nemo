"use client";

import { useEffect, useRef, useState } from "react";
import type * as ThreeNS from "three";
import { colors } from "@/theme/tokens";

type Props = {
  className?: string;
  /** Read out by screen readers in place of the canvas. */
  label?: string;
  /** Show the small "Drag to turn it" hint under the model. */
  hint?: boolean;
};

/** Device finish: a muted slate blue, mid-tone so it stands out from the light page, with a lighter front plate. */
const BODY = "#4E6984";
const PLATE = "#6A86A2";
const SEAM = "#1E2A36";
const LENS_GLASS = "#0E1620";
const DISPLAY_BG = "#0F1A26";

/**
 * Nemo in 3D, built in code to the measurements of the team's CAD enclosure (nemo.glb):
 * a 61 x 113 x 32 mm box with a front plate, an 11 mm camera opening, a 30 x 15 mm screen window,
 * a mic pinhole, two small eyelets and one button on the right side. Same layout, with cleaner edges and finish.
 * three.js is loaded only in the browser, only when this component mounts.
 * It sways gently on its own (not under reduced motion) and can be dragged sideways to turn it.
 * Vertical swipes still scroll the page on touch screens.
 */
export function DeviceModel({
  className,
  label = "Nemo, a small slate blue device about the size of a deck of cards, with a small screen near the top, a camera lens below it and a coral button on its side, shown in 3D.",
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
      // Wait for the brand fonts so the little screen is drawn in Poppins.
      await document.fonts.ready.catch(() => undefined);
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
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.95;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFShadowMap;
      const canvas = renderer.domElement;
      canvas.setAttribute("aria-hidden", "true");
      canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;touch-action:pan-y;cursor:grab;";
      wrap.appendChild(canvas);

      const scene = new THREE.Scene();
      const pmrem = new THREE.PMREMGenerator(renderer);
      const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      scene.environment = envTex;
      scene.environmentIntensity = 0.5;

      const camera = new THREE.PerspectiveCamera(28, 1, 1, 2000);

      const key = new THREE.DirectionalLight(0xffffff, 1.3);
      key.position.set(-20, 260, 90);
      key.castShadow = true;
      key.shadow.mapSize.set(1024, 1024);
      key.shadow.radius = 6;
      key.shadow.bias = -0.0005;
      Object.assign(key.shadow.camera, { near: 10, far: 600, left: -120, right: 120, top: 120, bottom: -120 });
      scene.add(key);

      // Turntable: `spin` turns around the vertical axis, `model` holds the device.
      const spin = new THREE.Group();
      scene.add(spin);

      const ground = new THREE.Mesh(new THREE.PlaneGeometry(800, 800), new THREE.ShadowMaterial({ opacity: 0.14 }));
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
        const dist = Math.max(distH, distW) * 1.04 + radiusXZ;
        const target = new THREE.Vector3(0, height * 0.5, 0);
        camera.position.set(0, height * 0.5 + dist * 0.18, dist);
        camera.lookAt(target);
        camera.updateProjectionMatrix();
      };

      const model = buildDevice(THREE);

      // Centre it on the turntable and stand it on the ground.
      const box = new THREE.Box3().setFromObject(model);
      const size = box.getSize(new THREE.Vector3());
      const centre = box.getCenter(new THREE.Vector3());
      model.position.set(-centre.x, -box.min.y, -centre.z);
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

/** Extrudes a shape into a slab with a small rounded edge. Its front face is at z = depth / 2. */
function slab(THREE: Three, shape: ThreeNS.Shape, depth: number, bevel: number) {
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: depth - bevel * 2,
    bevelEnabled: true,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelOffset: -bevel,
    bevelSegments: 6,
    curveSegments: 32,
  });
  geo.translate(0, 0, -(depth - bevel * 2) / 2);
  geo.computeVertexNormals();
  return geo;
}

function circlePath(THREE: Three, x: number, y: number, r: number) {
  const path = new THREE.Path();
  path.absarc(x, y, r, 0, Math.PI * 2, true);
  return path;
}

/** What the screen shows, like a small OLED display: the answer to "Where are my keys?". */
function drawScreen(THREE: Three) {
  const W = 800;
  const H = 400;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d");
  if (g) {
    const heading = getComputedStyle(document.documentElement).getPropertyValue("--font-poppins").trim() || "sans-serif";
    g.fillStyle = DISPLAY_BG;
    g.fillRect(0, 0, W, H);
    g.textBaseline = "middle";
    g.fillStyle = colors.coral;
    g.beginPath();
    g.arc(62, 92, 14, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = "rgba(247,243,236,0.72)";
    g.font = `500 54px ${heading}`;
    g.fillText("Keys \u00b7 20 min ago", 96, 94);
    g.fillStyle = colors.cream;
    let size = 118;
    g.font = `600 ${size}px ${heading}`;
    while (g.measureText("Kitchen table").width > W - 80 && size > 40) {
      size -= 4;
      g.font = `600 ${size}px ${heading}`;
    }
    g.fillText("Kitchen table", 40, 250);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

/**
 * Builds the device, front facing +z, in millimetres, matching the CAD enclosure.
 * Front, top to bottom: screen window, camera, mic pinhole. Eyelets at the camera end.
 */
function buildDevice(THREE: Three) {
  const group = new THREE.Group();
  const finish = (hex: string, extra: Partial<ThreeNS.MeshPhysicalMaterialParameters> = {}) =>
    new THREE.MeshPhysicalMaterial({ color: new THREE.Color(hex), roughness: 0.62, clearcoat: 0.15, clearcoatRoughness: 0.6, ...extra });
  const add = (geo: ThreeNS.BufferGeometry, mat: ThreeNS.Material, x = 0, y = 0, z = 0) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    group.add(m);
    return m;
  };

  // Overall size from the CAD: 61 x 113 mm footprint, 28.6 mm body + 3 mm front plate.
  const W = 61;
  const H = 113;
  const CORNER = 7;
  const BODY_D = 28.6;
  const PLATE_D = 3;
  const SEAM_GAP = 0.35;
  const BACK = -(BODY_D + PLATE_D + SEAM_GAP) / 2;
  const bodyFront = BACK + BODY_D;
  const plateBack = bodyFront + SEAM_GAP;

  // Feature positions (from the CAD, turned so the screen is above the camera).
  const SCREEN = { x: 0, y: 34, w: 30, h: 15 };
  const CAM = { x: 0, y: -20.5, r: 5.5 };
  const MIC = { x: 16, y: -40.5, r: 0.7 };
  const BUTTON_Y = 12;

  // Body
  add(slab(THREE, roundedRect(THREE, W, H, CORNER), BODY_D, 3), finish(BODY), 0, 0, BACK + BODY_D / 2);

  // The thin dark line where the front plate meets the body
  add(slab(THREE, roundedRect(THREE, W - 1.6, H - 1.6, CORNER - 0.8), SEAM_GAP + 1, 0.2), finish(SEAM), 0, 0, bodyFront + SEAM_GAP / 2);

  // Front plate, with real openings for the screen, camera and mic
  const plate = roundedRect(THREE, W, H, CORNER);
  const win = roundedRect(THREE, SCREEN.w, SCREEN.h, 1.6);
  const winPath = new THREE.Path(win.getPoints(12).map((p) => new THREE.Vector2(p.x + SCREEN.x, p.y + SCREEN.y)).reverse());
  plate.holes.push(winPath, circlePath(THREE, CAM.x, CAM.y, CAM.r), circlePath(THREE, MIC.x, MIC.y, MIC.r));
  add(slab(THREE, plate, PLATE_D, 0.8), finish(PLATE), 0, 0, plateBack + PLATE_D / 2);

  // Screen, set back inside its window
  add(new THREE.PlaneGeometry(SCREEN.w, SCREEN.h), finish(DISPLAY_BG, { roughness: 0.3 }), SCREEN.x, SCREEN.y, plateBack + 0.2);
  const display = add(
    new THREE.PlaneGeometry(SCREEN.w - 1.2, SCREEN.h - 1.2),
    new THREE.MeshBasicMaterial({ map: drawScreen(THREE), toneMapped: false }),
    SCREEN.x,
    SCREEN.y,
    plateBack + 0.6,
  );
  display.castShadow = false;
  add(
    new THREE.PlaneGeometry(SCREEN.w, SCREEN.h),
    new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.06, roughness: 0.05, clearcoat: 1 }),
    SCREEN.x,
    SCREEN.y,
    plateBack + 0.9,
  ).castShadow = false;

  // A thin brushed-metal trim around the camera opening
  const trim = add(new THREE.TorusGeometry(CAM.r + 0.5, 0.5, 16, 64), finish("#A9AEB3", { metalness: 0.85, roughness: 0.3 }), CAM.x, CAM.y, plateBack + PLATE_D - 0.1);
  trim.castShadow = false;

  // Camera: a dark metal barrel with a glossy lens, sitting just inside the opening
  const barrel = add(new THREE.CylinderGeometry(CAM.r - 0.2, CAM.r - 0.2, 3, 48), finish("#2B3138", { metalness: 0.6, roughness: 0.35 }), CAM.x, CAM.y, plateBack - 0.5);
  barrel.rotation.x = Math.PI / 2;
  const lensRing = add(new THREE.TorusGeometry(3.4, 0.45, 16, 48), finish("#8C949C", { metalness: 0.9, roughness: 0.25 }), CAM.x, CAM.y, plateBack + 1.05);
  lensRing.castShadow = false;
  const lens = add(
    new THREE.SphereGeometry(3.2, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshPhysicalMaterial({ color: LENS_GLASS, roughness: 0.05, clearcoat: 1, clearcoatRoughness: 0.03 }),
    CAM.x,
    CAM.y,
    plateBack + 1,
  );
  lens.rotation.x = Math.PI / 2;
  lens.scale.set(1, 0.4, 1);

  // The one button, on the right side: a coral cap in a dark seat
  const sideZ = BACK + BODY_D / 2;
  const seat = add(new THREE.CylinderGeometry(5.4, 5.4, 1.2, 48), finish(SEAM), W / 2 - 0.3, BUTTON_Y, sideZ);
  seat.rotation.z = Math.PI / 2;
  const cap = add(new THREE.CylinderGeometry(4.5, 4.7, 2.4, 48), finish(colors.coral, { roughness: 0.45, clearcoat: 0.4 }), W / 2 + 0.6, BUTTON_Y, sideZ);
  cap.rotation.z = Math.PI / 2;
  const dome = add(new THREE.SphereGeometry(4.5, 48, 16, 0, Math.PI * 2, 0, Math.PI / 2), finish(colors.coral, { roughness: 0.45, clearcoat: 0.4 }), W / 2 + 1.8, BUTTON_Y, sideZ);
  dome.rotation.z = -Math.PI / 2;
  dome.scale.set(1, 0.25, 1);

  // Mic: dark behind the pinhole
  add(new THREE.CircleGeometry(MIC.r + 0.3, 16), finish(SEAM), MIC.x, MIC.y, plateBack + 0.05);

  // Two small eyelets at the camera end, set into the back half of the body (as on the CAD)
  for (const x of [-24, 24]) {
    add(new THREE.TorusGeometry(2.4, 1.1, 16, 32), finish(BODY), x, -H / 2 - 1.2, BACK + 6);
  }

  // The back of the box stays plain, as on the CAD.
  return group;
}
