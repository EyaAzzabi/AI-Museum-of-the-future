import * as THREE from 'three';

const canvas = document.getElementById('museumCanvas');
const view = canvas.parentElement;
const loadState = document.getElementById('loadState');
const startButton = document.getElementById('startWalk');
const worldTitle = document.querySelector('.world-title');
const locationLabel = document.getElementById('worldLocation');
const roomButtons = document.getElementById('roomButtons');
const touchControls = document.getElementById('touchControls');
const movementHint = document.querySelector('.world-help span:first-child');
const agentTheme = document.getElementById('agentTheme');
const runAgentsButton = document.getElementById('runAgents');
const agentRunStatus = document.getElementById('agentRunStatus');
const agentResults = document.getElementById('agentResults');
const panelRoom = document.getElementById('panelRoom');
const panelTitle = document.getElementById('panelTitle');
const panelDescription = document.getElementById('panelDescription');
const panelEvidence = document.getElementById('panelEvidence');

const rooms = [
  { key: 'historian', agent: 'Historien', name: 'Le temps long', description: 'Les événements qui deviennent des tournants de l’Histoire.', palette: ['#c5a86e', '#4e6554', '#eee1bf'], type: 'sphere' },
  { key: 'sociologist', agent: 'Sociologue', name: 'Vies en mouvement', description: 'Les trajectoires humaines, les migrations et les transformations de la société.', palette: ['#8e9c7c', '#af765f', '#e3d1ad'], type: 'torus' },
  { key: 'technology', agent: 'Technologies', name: 'Le monde de demain', description: 'Les innovations et les sciences qui transforment notre quotidien.', palette: ['#698c95', '#d09a60', '#d7d8c8'], type: 'crystal' },
  { key: 'culture_art', agent: 'Culture & arts', name: 'L’esprit d’une époque', description: 'Les créations, les images et les récits qui donnent forme à une culture.', palette: ['#b8795d', '#d2ba8b', '#4b586e'], type: 'knot' },
  { key: 'visual', agent: 'Agent visuel', name: 'Voir notre monde', description: 'Les traces visuelles par lesquelles les générations futures reconnaîtront notre temps.', palette: ['#71899a', '#b58e6e', '#d9cda9'], type: 'octahedron' },
];
const agentLabels = {
  historian: 'Historien',
  sociologist: 'Sociologue',
  technology: 'Technologies',
  culture_art: 'Culture & arts',
  visual: 'Agent visuel',
  reviewer: 'Relecture croisée',
  curator: 'Conservateur',
  fact_checker: 'Vérificateur de faits',
};
const agentStatusLabels = {
  complete: 'Analyse terminée',
  no_evidence: 'Aucune conclusion sourcée',
  error: 'Erreur pendant l’analyse',
  unavailable: 'Étape non exécutée',
};

const scene = new THREE.Scene();
scene.background = new THREE.Color('#171a17');
scene.fog = new THREE.FogExp2('#171a17', 0.014);

const camera = new THREE.PerspectiveCamera(72, 1, 0.1, 100);
camera.position.set(0, 1.66, 0);
camera.rotation.y = Math.PI;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const clock = new THREE.Clock();
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const interactiveTargets = [];
const roomGroups = [];
const sceneArtworks = [];
const imageLoader = new THREE.TextureLoader();
imageLoader.setCrossOrigin('anonymous');
const heldKeys = new Set();
const isSmallScreen = window.matchMedia('(max-width: 680px)');
let exhibitPresets = [];
let hoveredTarget = null;
let lookPointer = null;
let previousTouchPosition = { x: 0, y: 0 };
let didLookDrag = false;
let walkMode = false;
camera.rotation.order = 'YXZ';

function material(color, roughness = 0.75, metalness = 0) {
  return new THREE.MeshStandardMaterial({ color, roughness, metalness });
}

function addBox(parent, size, position, surface, rotationY = 0) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), surface);
  mesh.position.set(...position);
  mesh.rotation.y = rotationY;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function createTileMap() {
  const tile = document.createElement('canvas');
  tile.width = 384;
  tile.height = 384;
  const context = tile.getContext('2d');
  context.fillStyle = '#aaa494';
  context.fillRect(0, 0, 384, 384);
  context.strokeStyle = 'rgba(70,65,55,.25)';
  context.lineWidth = 3;
  context.strokeRect(2, 2, 380, 380);
  context.lineWidth = 1;
  context.strokeStyle = 'rgba(255,250,233,.3)';
  context.strokeRect(8, 8, 368, 368);
  for (let i = 0; i < 12000; i += 1) {
    const shade = Math.random() > 0.5 ? 255 : 30;
    context.fillStyle = `rgba(${shade},${shade},${shade},${Math.random() * 0.035})`;
    context.fillRect(Math.random() * 384, Math.random() * 384, 2, 2);
  }
  const texture = new THREE.CanvasTexture(tile);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1, 1);
  return texture;
}

function addFloor(parent, width, depth, z = 0) {
  const tile = new THREE.Mesh(
    new THREE.PlaneGeometry(width, depth),
    new THREE.MeshStandardMaterial({ map: createTileMap(), roughness: 0.34, metalness: 0.08 }),
  );
  tile.rotation.x = -Math.PI / 2;
  tile.position.set(0, 0.04, z);
  tile.receiveShadow = true;
  parent.add(tile);
}

function makePaintingTexture(palette, seed) {
  const art = document.createElement('canvas');
  art.width = 512;
  art.height = 384;
  const context = art.getContext('2d');
  const gradient = context.createLinearGradient(0, 0, 512, 384);
  gradient.addColorStop(0, palette[0]);
  gradient.addColorStop(0.52, palette[1]);
  gradient.addColorStop(1, palette[2]);
  context.fillStyle = gradient;
  context.fillRect(0, 0, art.width, art.height);

  let randomSeed = seed * 7919 + 31;
  const random = () => {
    randomSeed = (randomSeed * 16807) % 2147483647;
    return (randomSeed - 1) / 2147483646;
  };
  for (let i = 0; i < 46; i += 1) {
    const color = palette[Math.floor(random() * palette.length)];
    context.globalAlpha = 0.16 + random() * 0.42;
    context.strokeStyle = color;
    context.lineWidth = 8 + random() * 52;
    context.lineCap = 'round';
    context.beginPath();
    const x = random() * art.width;
    const y = random() * art.height;
    context.moveTo(x, y);
    context.bezierCurveTo(
      x + (random() - 0.5) * 340,
      y + (random() - 0.5) * 240,
      random() * art.width,
      random() * art.height,
      random() * art.width,
      random() * art.height,
    );
    context.stroke();
  }
  context.globalAlpha = 0.55;
  context.fillStyle = palette[2];
  context.beginPath();
  context.ellipse(260, 185, 70 + random() * 65, 95 + random() * 70, random(), 0, Math.PI * 2);
  context.fill();
  context.globalAlpha = 1;
  const texture = new THREE.CanvasTexture(art);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function drawWrappedText(context, text, x, y, width, lineHeight, maxLines, font, color) {
  context.font = font;
  context.fillStyle = color;
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const lines = [];
  let currentLine = '';
  let truncated = false;
  for (const word of words) {
    const candidate = currentLine ? `${currentLine} ${word}` : word;
    if (currentLine && context.measureText(candidate).width > width) {
      lines.push(currentLine);
      currentLine = word;
      if (lines.length === maxLines) {
        truncated = true;
        break;
      }
    } else {
      currentLine = candidate;
    }
  }
  if (currentLine && lines.length < maxLines) lines.push(currentLine);
  lines.forEach((line, index) => {
    let renderedLine = line;
    if (truncated && index === lines.length - 1) {
      while (renderedLine && context.measureText(`${renderedLine}…`).width > width) {
        renderedLine = renderedLine.slice(0, -1);
      }
      renderedLine += '…';
    }
    context.fillText(renderedLine, x, y + index * lineHeight);
  });
  return y + lines.length * lineHeight;
}

function makeArchiveTexture(title, description, palette, label, reference) {
  const artwork = document.createElement('canvas');
  artwork.width = 512;
  artwork.height = 384;
  const context = artwork.getContext('2d');
  context.fillStyle = '#eee8d9';
  context.fillRect(0, 0, artwork.width, artwork.height);
  context.fillStyle = palette[0];
  context.fillRect(0, 0, 15, artwork.height);
  context.strokeStyle = `${palette[1]}88`;
  context.lineWidth = 2;
  context.beginPath();
  context.arc(445, 92, 62, Math.PI, Math.PI * 2);
  context.stroke();
  context.fillStyle = '#71664f';
  context.font = 'bold 16px sans-serif';
  context.fillText(String(label || 'ARCHIVES DU MUSÉE').toLocaleUpperCase('fr'), 34, 39);
  const titleBottom = drawWrappedText(context, title, 34, 92, 440, 42, 2, '500 34px Georgia, serif', '#1f3027');
  drawWrappedText(context, description, 34, titleBottom + 9, 440, 25, 3, '18px sans-serif', '#41483f');
  context.fillStyle = '#8b7956';
  context.font = '12px sans-serif';
  context.fillText(String(reference || 'COLLECTION DU MUSÉE').slice(0, 62).toLocaleUpperCase('fr'), 34, 355);
  const texture = new THREE.CanvasTexture(artwork);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function addPainting(parent, room, roomIndex, position, rotationY, variant) {
  const frame = new THREE.Group();
  frame.position.set(...position);
  frame.rotation.y = rotationY;
  parent.add(frame);

  const width = variant === 0 ? 3.05 : 2.55;
  const height = variant === 0 ? 2.35 : 1.95;
  const bronze = material('#ae9563', 0.34, 0.62);
  const backing = material('#302b22', 0.72);
  addBox(frame, [width + 0.34, height + 0.34, 0.12], [0, 0, -0.045], backing);
  addBox(frame, [width + 0.18, 0.09, 0.13], [0, height / 2 + 0.045, 0.025], bronze);
  addBox(frame, [width + 0.18, 0.09, 0.13], [0, -height / 2 - 0.045, 0.025], bronze);
  addBox(frame, [0.09, height, 0.13], [-width / 2 - 0.045, 0, 0.025], bronze);
  addBox(frame, [0.09, height, 0.13], [width / 2 + 0.045, 0, 0.025], bronze);

  const presetChunk = room.preset?.chunks?.[variant] || room.preset?.chunks?.[0];
  const texture = presetChunk
    ? makeArchiveTexture(room.preset.title, presetChunk.content, room.palette, `ARCHIVES · ${variant + 1}`, presetChunk.metadata?.source)
    : makePaintingTexture(room.palette, roomIndex * 3 + variant);
  const artwork = new THREE.Mesh(
    new THREE.PlaneGeometry(width - 0.08, height - 0.08),
    new THREE.MeshBasicMaterial({
      map: texture,
      side: THREE.DoubleSide,
    }),
  );
  artwork.position.z = 0.04;
  artwork.userData = {
    roomIndex,
    exhibit: room.preset || null,
    artworkVariant: variant,
    isPrimary: room.key === 'visual' || (variant < 3 && position[0] !== -5.665 && position[0] !== 5.665),
  };
  frame.add(artwork);
  interactiveTargets.push(artwork);
  sceneArtworks.push(artwork);
  if (artwork.userData.isPrimary && presetChunk?.metadata?.image_url) {
    loadArtworkImage(artwork, presetChunk.metadata.image_url, () => !artwork.userData.section);
  }
}

function addSculpture(parent, room, roomIndex) {
  const brass = material(room.palette[0], 0.3, 0.58);
  const dark = material('#4a463d', 0.45, 0.2);
  const plinth = new THREE.Mesh(new THREE.BoxGeometry(1.75, 0.95, 1.75), material('#d4cbb8', 0.39));
  plinth.position.set(-2.9, 0.52, -6.1);
  plinth.receiveShadow = true;
  plinth.castShadow = true;
  parent.add(plinth);
  addBox(parent, [1.95, 0.09, 1.95], [-2.9, 1.03, -6.1], brass);

  const sculpture = new THREE.Group();
  sculpture.position.set(-2.9, 1.18, -6.1);
  parent.add(sculpture);
  if (room.type === 'torus') {
    const loop = new THREE.Mesh(new THREE.TorusKnotGeometry(0.53, 0.16, 100, 14), brass);
    loop.rotation.x = 0.35;
    sculpture.add(loop);
  } else if (room.type === 'crystal' || room.type === 'octahedron') {
    const crystal = new THREE.Mesh(new THREE.OctahedronGeometry(0.7, 0), brass);
    crystal.scale.set(0.78, 1.35, 0.78);
    crystal.rotation.y = 0.45;
    sculpture.add(crystal);
    const inset = new THREE.Mesh(new THREE.IcosahedronGeometry(0.29, 1), dark);
    inset.position.y = 0.04;
    sculpture.add(inset);
  } else if (room.type === 'knot') {
    const loop = new THREE.Mesh(new THREE.TorusKnotGeometry(0.45, 0.13, 120, 14, 2, 5), brass);
    loop.rotation.x = -0.48;
    sculpture.add(loop);
  } else {
    const orb = new THREE.Mesh(new THREE.IcosahedronGeometry(0.59, 2), brass);
    orb.scale.set(0.78, 1.3, 0.78);
    sculpture.add(orb);
    const orbit = new THREE.Mesh(new THREE.TorusGeometry(0.78, 0.035, 8, 80), dark);
    orbit.rotation.set(0.7, 0.4, -0.35);
    sculpture.add(orbit);
  }
  sculpture.traverse(object => {
    if (object.isMesh) {
      object.castShadow = true;
      object.userData = { roomIndex, exhibit: room.preset || null };
      interactiveTargets.push(object);
    }
  });

  const secondaryPlinth = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.74, 1.4), material('#d4cbb8', 0.39));
  secondaryPlinth.position.set(2.85, 0.4, -8.5);
  secondaryPlinth.castShadow = true;
  secondaryPlinth.receiveShadow = true;
  parent.add(secondaryPlinth);
  addBox(parent, [1.58, 0.08, 1.58], [2.85, 0.81, -8.5], brass);
  const secondaryArtifact = new THREE.Mesh(
    new THREE.TorusKnotGeometry(0.38, 0.1, 80, 10, 2, 3),
    brass,
  );
  secondaryArtifact.position.set(2.85, 1.26, -8.5);
  secondaryArtifact.rotation.x = 0.4;
  secondaryArtifact.castShadow = true;
  secondaryArtifact.userData = { roomIndex, exhibit: room.preset || null, artworkVariant: 1 };
  parent.add(secondaryArtifact);
  interactiveTargets.push(secondaryArtifact);
}

function addCentralRotunda() {
  const floor = new THREE.Mesh(
    new THREE.CylinderGeometry(5.2, 5.35, 0.22, 96),
    material('#beb49b', 0.36, 0.1),
  );
  floor.position.y = -0.08;
  floor.receiveShadow = true;
  scene.add(floor);

  const goldLine = new THREE.Mesh(
    new THREE.TorusGeometry(4.35, 0.035, 8, 128),
    material('#b99c65', 0.3, 0.7),
  );
  goldLine.rotation.x = Math.PI / 2;
  goldLine.position.y = 0.045;
  scene.add(goldLine);

  const wall = material('#d2ccbc', 0.84);
  const trim = material('#9b8357', 0.4, 0.45);
  const segments = 112;
  const doorwayHalfAngle = Math.asin(2.15 / 5.2);
  for (let i = 0; i < segments; i += 1) {
    const angle = (i / segments) * Math.PI * 2;
    const hasDoorway = rooms.some((_, index) => {
      const target = (index * Math.PI * 2) / rooms.length;
      const delta = Math.atan2(Math.sin(angle - target), Math.cos(angle - target));
      return Math.abs(delta) < doorwayHalfAngle;
    });
    if (hasDoorway) continue;

    const rotation = angle + Math.PI / segments;
    const radius = 5.2;
    const segment = new THREE.Mesh(
      new THREE.BoxGeometry((Math.PI * 2 * radius) / segments + 0.045, 5.2, 0.4),
      wall,
    );
    segment.position.set(Math.sin(rotation) * radius, 2.52, Math.cos(rotation) * radius);
    segment.rotation.y = rotation;
    segment.castShadow = true;
    segment.receiveShadow = true;
    scene.add(segment);

    if (i % 4 === 0) {
      const pilaster = new THREE.Mesh(new THREE.BoxGeometry(0.12, 4.9, 0.48), trim);
      pilaster.position.set(Math.sin(rotation) * radius, 2.49, Math.cos(rotation) * radius);
      pilaster.rotation.y = rotation;
      pilaster.castShadow = true;
      scene.add(pilaster);
    }
  }

  const ceiling = new THREE.Mesh(new THREE.CylinderGeometry(5.2, 5.2, 0.24, 96, 1, true), material('#46483d', 0.87));
  ceiling.position.y = 5.25;
  scene.add(ceiling);

  const chandelier = new THREE.Group();
  chandelier.position.set(0, 4.65, 0);
  scene.add(chandelier);
  const hoop = new THREE.Mesh(new THREE.TorusGeometry(1.25, 0.045, 8, 64), trim);
  hoop.rotation.x = Math.PI / 2;
  chandelier.add(hoop);
  for (let i = 0; i < 8; i += 1) {
    const angle = (i / 8) * Math.PI * 2;
    const bulb = new THREE.Mesh(
      new THREE.SphereGeometry(0.11, 12, 8),
      new THREE.MeshStandardMaterial({ color: '#f6d99d', emissive: '#d7a65e', emissiveIntensity: 1.3 }),
    );
    bulb.position.set(Math.cos(angle) * 1.22, -0.2, Math.sin(angle) * 1.22);
    chandelier.add(bulb);
  }
  const centerLight = new THREE.PointLight('#f8dfb0', 80, 15, 1.8);
  centerLight.position.set(0, 4.25, 0);
  scene.add(centerLight);
  scene.add(new THREE.AmbientLight('#f4ead3', 1.35));
  const hemisphere = new THREE.HemisphereLight('#e8e4d4', '#665846', 2);
  scene.add(hemisphere);
}

function addGallery(room, index) {
  const angle = (index * Math.PI * 2) / rooms.length;
  const radius = 5.2;
  const group = new THREE.Group();
  group.position.set(Math.sin(angle) * radius, 0, Math.cos(angle) * radius);
  group.rotation.y = angle + Math.PI;
  group.userData.roomIndex = index;
  scene.add(group);
  roomGroups.push(group);

  const plaster = material('#d8d1c1', 0.88);
  const darkStone = material('#413e35', 0.74);
  const timber = material('#654d31', 0.5, 0.12);
  const brass = material('#ac915e', 0.34, 0.62);
  addFloor(group, 12, 15, -7.5);
  addBox(group, [12, 0.27, 0.36], [0, 0.16, -14.82], darkStone);
  addBox(group, [12, 0.08, 0.28], [0, 0.28, -14.72], brass);

  addBox(group, [4, 5.1, 0.45], [-4, 2.56, 0.03], plaster);
  addBox(group, [4, 5.1, 0.45], [4, 2.56, 0.03], plaster);
  addBox(group, [4, 0.65, 0.45], [0, 4.84, 0.03], plaster);
  addBox(group, [0.34, 5.2, 14.9], [-5.86, 2.6, -7.45], plaster);
  addBox(group, [0.34, 5.2, 14.9], [5.86, 2.6, -7.45], plaster);
  addBox(group, [12, 5.2, 0.45], [0, 2.6, -14.92], plaster);
  addBox(group, [12.1, 0.26, 15.1], [0, 5.08, -7.45], plaster);
  addBox(group, [0.17, 5.2, 14.8], [-5.63, 2.6, -7.45], timber);
  addBox(group, [0.17, 5.2, 14.8], [5.63, 2.6, -7.45], timber);

  for (const side of [-1, 1]) {
    const column = new THREE.Mesh(new THREE.BoxGeometry(0.34, 4.7, 0.34), brass);
    column.position.set(side * 2.08, 2.55, 0.07);
    column.castShadow = true;
    group.add(column);
    addBox(group, [0.55, 0.18, 0.5], [side * 2.08, 4.95, 0.07], timber);
  }

  addBox(group, [0.12, 0.12, 15], [-5.48, 0.23, -7.45], brass);
  addBox(group, [0.12, 0.12, 15], [5.48, 0.23, -7.45], brass);
  const paintingLayout = [
    { position: [0, 3.0, -14.65], rotationY: 0 },
    { position: [-3.72, 2.85, -14.65], rotationY: 0 },
    { position: [3.72, 2.85, -14.65], rotationY: 0 },
    { position: [-5.665, 3.0, -3.2], rotationY: Math.PI / 2 },
    { position: [-5.665, 3.0, -7.5], rotationY: Math.PI / 2 },
    { position: [-5.665, 3.0, -11.8], rotationY: Math.PI / 2 },
    { position: [5.665, 3.0, -3.2], rotationY: -Math.PI / 2 },
    { position: [5.665, 3.0, -7.5], rotationY: -Math.PI / 2 },
    { position: [5.665, 3.0, -11.8], rotationY: -Math.PI / 2 },
  ];
  paintingLayout.forEach(({ position, rotationY }, variant) => {
    addPainting(group, room, index, position, rotationY, variant);
  });
  addSculpture(group, room, index);

  for (let i = 0; i < 3; i += 1) {
    const z = -3.2 - i * 4.7;
    const fixture = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.55, 0.18, 24), timber);
    fixture.position.set(0, 4.87, z);
    fixture.castShadow = true;
    group.add(fixture);
    const shade = new THREE.Mesh(
      new THREE.CircleGeometry(0.38, 24),
      new THREE.MeshBasicMaterial({ color: '#ffe0a1', side: THREE.DoubleSide }),
    );
    shade.rotation.x = Math.PI / 2;
    shade.position.set(0, 4.75, z);
    group.add(shade);
    const light = new THREE.PointLight('#f6d8a0', 24, 8.5, 1.8);
    light.position.set(0, 4.35, z);
    group.add(light);
  }

  const title = new THREE.Mesh(
    new THREE.BoxGeometry(2.9, 0.12, 0.04),
    new THREE.MeshStandardMaterial({ color: '#c5a86e', emissive: '#6d552e', emissiveIntensity: 0.2 }),
  );
  title.position.set(0, 4.24, 0.25);
  group.add(title);

  const marker = new THREE.PointLight(room.palette[0], 10, 4, 2);
  marker.position.set(0, 3.65, 0.25);
  group.add(marker);
}

function loadPresets() {
  return fetch('/api/historian/presets')
    .then(response => {
      if (!response.ok) throw new Error(`Archive service returned ${response.status}`);
      return response.json();
    })
    .then(data => {
      exhibitPresets = Array.isArray(data.presets) ? data.presets : [];
      const visualCollection = {
        title: 'Images des archives',
        chunks: exhibitPresets.flatMap(preset => preset.chunks || []).filter(chunk => chunk.metadata?.image_url),
      };
      const assign = [
        exhibitPresets.find(item => item.id === 'tunisia_2021_constitution'),
        exhibitPresets.find(item => item.id === 'tunisia_migration'),
        null,
        exhibitPresets.find(item => item.id === 'tunisia_cinema'),
        visualCollection.chunks.length ? visualCollection : null,
      ];
      rooms.forEach((room, index) => { room.preset = assign[index] || null; });
      agentTheme.replaceChildren();
      exhibitPresets.forEach((preset, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = preset.title;
        agentTheme.append(option);
      });
      runAgentsButton.disabled = exhibitPresets.length === 0;
      if (!exhibitPresets.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Aucune archive disponible';
        agentTheme.append(option);
      }
    })
    .catch(error => {
      console.warn('Museum archives could not be loaded:', error);
      rooms.forEach(room => { room.preset = null; });
      agentTheme.replaceChildren();
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'Archives indisponibles';
      agentTheme.append(option);
      runAgentsButton.disabled = true;
    });
}

function safeImageUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return '';
  try {
    const url = new URL(value, window.location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}

function exhibitImageMetadata(artifact) {
  const item = artifact && typeof artifact === 'object' ? artifact : {};
  const artifactId = typeof artifact === 'string' ? artifact : item.id;
  const sourceChunk = exhibitPresets
    .flatMap(preset => preset.chunks || [])
    .find(chunk => chunk.chunk_id === artifactId);
  const metadata = { ...(sourceChunk?.metadata || {}), ...(item.metadata || {}) };
  return {
    url: safeImageUrl(metadata.image_url || item.image_url),
    alt: metadata.image_alt || item.image_alt || item.title || '',
    credit: metadata.image_credit || item.image_credit || '',
    source: metadata.image_source || item.image_source || '',
  };
}

function loadArtworkImage(artwork, imageUrl, isCurrent) {
  const safeUrl = safeImageUrl(imageUrl);
  if (!safeUrl) return;
  imageLoader.load(safeUrl, texture => {
    if (!isCurrent()) {
      texture.dispose();
      return;
    }
    texture.colorSpace = THREE.SRGBColorSpace;
    const imageAspect = texture.image.width / texture.image.height;
    const frameAspect = artwork.geometry.parameters.width / artwork.geometry.parameters.height;
    if (imageAspect > frameAspect) {
      const visibleWidth = frameAspect / imageAspect;
      texture.repeat.set(visibleWidth, 1);
      texture.offset.set((1 - visibleWidth) / 2, 0);
    } else {
      const visibleHeight = imageAspect / frameAspect;
      texture.repeat.set(1, visibleHeight);
      texture.offset.set(0, (1 - visibleHeight) / 2);
    }
    artwork.material.map?.dispose();
    artwork.material.map = texture;
    artwork.material.needsUpdate = true;
  }, undefined, () => {});
}

function renderExhibitionInScene(data) {
  const sections = data.exhibition?.sections || [];
  const catalog = new Map((data.artifacts || []).filter(item => item?.id).map(item => [item.id, item]));
  const sectionForArtifact = new Map();
  sections.forEach(section => {
    (section.artifacts || []).forEach(rawArtifact => {
      const artifact = rawArtifact && typeof rawArtifact === 'object' ? rawArtifact : { id: rawArtifact || '' };
      if (!artifact.id) return;
      catalog.set(artifact.id, { ...(catalog.get(artifact.id) || {}), ...artifact });
      if (!sectionForArtifact.has(artifact.id)) sectionForArtifact.set(artifact.id, section);
    });
  });

  const presetById = new Map();
  exhibitPresets.forEach(preset => {
    (preset.chunks || []).forEach(chunk => {
      const metadata = chunk.metadata || {};
      presetById.set(chunk.chunk_id, {
        id: chunk.chunk_id,
        title: metadata.title || preset.title,
        content: chunk.content,
        source: metadata.source,
        category: metadata.category,
        year: metadata.year,
        url: metadata.url,
        metadata,
      });
    });
  });
  presetById.forEach((artifact, id) => {
    const current = catalog.get(id) || {};
    catalog.set(id, {
      ...artifact,
      ...current,
      title: current.title || artifact.title,
      content: current.content || artifact.content,
      metadata: { ...(current.metadata || {}), ...artifact.metadata },
    });
  });

  const presetOwner = new Map();
  rooms.forEach(room => {
    (room.preset?.chunks || []).forEach(chunk => {
      if (!presetOwner.has(chunk.chunk_id)) presetOwner.set(chunk.chunk_id, room.key);
    });
  });
  const claimed = new Set();
  const exhibitsByRoom = new Map();
  rooms.forEach(room => {
    const agent = (data.agents || []).find(item => item.name === room.key);
    const selected = (agent?.selected_artifacts || [])
      .map(id => catalog.get(id))
      .filter(artifact => artifact && !claimed.has(artifact.id)
        && (!presetOwner.has(artifact.id) || presetOwner.get(artifact.id) === room.key));
    const fallback = (room.preset?.chunks || [])
      .map(chunk => catalog.get(chunk.chunk_id))
      .filter(artifact => artifact && !claimed.has(artifact.id));
    let artifacts = [...new Map([...selected, ...fallback].map(artifact => [artifact.id, artifact])).values()];
    if (!artifacts.length && room.key === 'visual') {
      artifacts = (room.preset?.chunks || []).map(chunk => catalog.get(chunk.chunk_id)).filter(Boolean);
    }
    artifacts.forEach(artifact => claimed.add(artifact.id));
    exhibitsByRoom.set(room.key, artifacts.map(artifact => {
      const relatedSection = sectionForArtifact.get(artifact.id);
      const finding = agent?.findings?.find(text => text.includes(`[${artifact.id}]`));
      return {
        artifact,
        section: {
          title: relatedSection?.title || artifact.title || room.name,
          narrative: finding || relatedSection?.narrative || artifact.content || agent?.perspective || room.description,
        },
      };
    }));
  });

  if (!sections.length && !data.artifacts?.length && ![...exhibitsByRoom.values()].some(items => items.length)) return;
  rooms.forEach(room => {
    const roomArtworks = sceneArtworks.filter(artwork => rooms[artwork.userData.roomIndex].key === room.key);
    const exhibits = exhibitsByRoom.get(room.key) || [];

    roomArtworks.forEach((artwork, slotIndex) => {
      const selected = exhibits[slotIndex];
      if (!selected) return;

      const { section, artifact } = selected;
      const image = exhibitImageMetadata(artifact);
      const reference = [artifact.source, artifact.year, artifact.id, image.credit].filter(Boolean).join(' · ');
      const archiveTexture = makeArchiveTexture(
        artifact.title || section.title || data.exhibition?.title || room.name,
        section.narrative || artifact.content || '',
        room.palette,
        `${room.agent.toLocaleUpperCase('fr')} · ${artifact.category || 'ARCHIVES'}`,
        reference,
      );
      const oldTexture = artwork.material.map;
      artwork.material.map = archiveTexture;
      artwork.material.color.set('#ffffff');
      artwork.material.needsUpdate = true;
      oldTexture?.dispose();
      artwork.userData.section = section;
      artwork.userData.artifact = artifact;

      if (!image.url || !artwork.userData.isPrimary) return;
      loadArtworkImage(artwork, image.url, () => artwork.userData.section === section);
    });
  });

  const title = data.exhibition?.title || (data.partial ? 'Analyses partielles des agents' : 'Exposition du musée');
  locationLabel.textContent = `EXPOSITION · ${title}`;
}

function renderRoomNavigation() {
  roomButtons.innerHTML = rooms.map((room, index) => `
    <button type="button" data-room="${index}" aria-current="${index === 0}">
      <span class="room-number">${String(index + 1).padStart(2, '0')}</span>
      <span class="room-name">${room.name}</span>
      <span class="room-agent">${room.agent}</span>
    </button>
  `).join('');
  roomButtons.querySelectorAll('button').forEach(button => {
    button.addEventListener('click', () => enterRoom(Number(button.dataset.room)));
  });
}

function enterRoom(index) {
  const group = roomGroups[index];
  const localPosition = new THREE.Vector3(0, 1.66, -4.1);
  group.localToWorld(localPosition);
  camera.position.copy(localPosition);
  camera.rotation.set(0, group.rotation.y, 0);
  selectRoom(index);
  worldTitle.classList.add('is-hidden');
}

function setWalkMode(enabled) {
  walkMode = enabled;
  view.classList.toggle('is-walking', enabled);
  if (enabled) {
    worldTitle.classList.add('is-hidden');
    startButton.innerHTML = '<span aria-hidden="true">×</span> Quitter la visite';
  } else {
    heldKeys.clear();
    startButton.innerHTML = '<span aria-hidden="true">↗</span> Entrer dans le musée';
  }
}

function selectRoom(index) {
  const room = rooms[index];
  locationLabel.textContent = `SALLE ${String(index + 1).padStart(2, '0')} · ${room.agent.toLocaleUpperCase('fr')}`;
  roomButtons.querySelectorAll('button').forEach(button => {
    button.setAttribute('aria-current', String(Number(button.dataset.room) === index));
  });
  panelRoom.textContent = `${String(index + 1).padStart(2, '0')} · ${room.agent.toLocaleUpperCase('fr')}`;
  panelTitle.textContent = room.preset?.title || room.name;
  panelDescription.textContent = room.preset
    ? `${room.description} Cette salle présente ${room.preset.chunks.length} archives de la collection. Cliquez sur une œuvre pour en lire un extrait.`
    : room.description;
  panelEvidence.replaceChildren();
  panelEvidence.hidden = true;
  worldTitle.classList.add('is-hidden');
}

function describeExhibit(target) {
  const index = target.userData.roomIndex;
  const room = rooms[index];
  const preset = target.userData.exhibit || room.preset;
  selectRoom(index);
  if (target.userData.section) {
    const section = target.userData.section;
    const artifact = target.userData.artifact || {};
    panelTitle.textContent = artifact.title || section.title || room.name;
    panelDescription.textContent = section.narrative || room.description;
    const meta = document.createElement('span');
    meta.className = 'evidence-meta';
    const imageMetadata = exhibitImageMetadata(artifact);
    meta.textContent = [artifact.source || 'ARCHIVES DU MUSÉE', artifact.year, artifact.id, imageMetadata.credit].filter(Boolean).join(' · ');
    const copy = document.createElement('p');
    copy.className = 'evidence-copy';
    copy.textContent = artifact.content || section.narrative || '';
    const content = [meta, copy];
    if (imageMetadata.url) {
      const imageElement = document.createElement('img');
      imageElement.className = 'evidence-image';
      imageElement.src = imageMetadata.url;
      imageElement.alt = imageMetadata.alt || artifact.title || section.title || 'Image d’archive';
      imageElement.addEventListener('error', () => imageElement.remove(), { once: true });
      content.unshift(imageElement);
    }
    if (imageMetadata.source) {
      const source = document.createElement('a');
      source.className = 'evidence-source-link';
      source.href = imageMetadata.source;
      source.target = '_blank';
      source.rel = 'noopener noreferrer';
      source.textContent = 'Voir la source et la licence de l’image ↗';
      content.push(source);
    }
    panelEvidence.replaceChildren(...content);
    panelEvidence.hidden = false;
    return;
  }
  panelTitle.textContent = preset?.title || room.name;
  panelDescription.textContent = preset
    ? room.description
    : `${room.description} Cette œuvre est une création visuelle générative, conçue comme interprétation de la salle — ce n’est pas un objet d’archive.`;

  const chunk = preset?.chunks?.[target.userData.artworkVariant || 0] || preset?.chunks?.[0];
  if (chunk) {
    const meta = document.createElement('span');
    meta.className = 'evidence-meta';
    meta.textContent = `ARCHIVE · ${String(chunk.metadata?.source || 'COLLECTION').toLocaleUpperCase('fr')}`;
    const copy = document.createElement('p');
    copy.className = 'evidence-copy';
    copy.textContent = chunk.content || chunk.text || 'Archive de la collection.';
    panelEvidence.replaceChildren(meta, copy);
    panelEvidence.hidden = false;
  }
}

function appendAgentCard(agent, providerRateLimited, artifactsById) {
  const card = document.createElement('article');
  card.className = 'agent-result-card';
  card.dataset.status = agent.status || 'unavailable';

  const heading = document.createElement('div');
  heading.className = 'agent-result-heading';
  const name = document.createElement('span');
  name.className = 'agent-result-name';
  name.textContent = agentLabels[agent.name] || agent.name;
  const status = document.createElement('span');
  status.className = 'agent-result-state';
  status.textContent = agent.status === 'error' && providerRateLimited
    ? 'Quota fournisseur atteint'
    : agentStatusLabels[agent.status] || 'État inconnu';
  heading.append(name, status);
  card.append(heading);

  if (agent.perspective) {
    const perspective = document.createElement('p');
    perspective.className = 'agent-result-copy';
    perspective.textContent = agent.perspective;
    card.append(perspective);
  }

  if (Array.isArray(agent.findings) && agent.findings.length) {
    const findings = document.createElement('ul');
    findings.className = 'agent-result-findings';
    agent.findings.forEach(text => {
      const item = document.createElement('li');
      item.textContent = text;
      findings.append(item);
    });
    card.append(findings);
  } else if (agent.status === 'error' && providerRateLimited) {
    const note = document.createElement('p');
    note.className = 'agent-result-copy';
    note.textContent = 'Le fournisseur IA a atteint sa limite de tokens. Réessayez après la réinitialisation du quota.';
    card.append(note);
  } else if (agent.status === 'no_evidence') {
    const note = document.createElement('p');
    note.className = 'agent-result-copy';
    note.textContent = 'Le spécialiste n’a pas trouvé de conclusion qu’il puisse relier aux archives chargées.';
    card.append(note);
  }

  const selectedArticles = (agent.selected_artifacts || [])
    .map(id => artifactsById.get(id)?.title || id);
  if (selectedArticles.length) {
    const sources = document.createElement('p');
    sources.className = 'agent-result-copy';
    sources.textContent = `Articles retenus : ${selectedArticles.join(' · ')}`;
    card.append(sources);
  }
  return card;
}

function renderAgentRun(data, preset) {
  renderExhibitionInScene(data);
  const providerRateLimited = /429|rate.?limit|tokens per day|\bTPD\b/i.test(data.error || '');
  const artifactsById = new Map((data.artifacts || []).map(artifact => [artifact.id, artifact]));
  const completedSpecialists = data.agents.filter(agent => (
    ['historian', 'sociologist', 'technology', 'culture_art', 'visual'].includes(agent.name)
    && agent.status === 'complete'
  )).length;
  const summary = document.createElement('div');
  summary.className = 'agent-exhibition';
  const title = document.createElement('h3');
  title.textContent = data.exhibition?.title || preset.title;
  const concept = document.createElement('p');
  concept.textContent = data.exhibition?.concept
    || `${completedSpecialists}/5 spécialistes ont produit une analyse appuyée sur ces archives.`;
  const duration = document.createElement('p');
  duration.className = 'agent-run-hint';
  duration.textContent = `Thème : ${preset.title}${Number.isFinite(data.duration_s) ? ` · ${Math.round(data.duration_s)} s` : ''}`;
  summary.append(title, concept, duration);

  if (Array.isArray(data.exhibition?.sections) && data.exhibition.sections.length) {
    const sectionHeading = document.createElement('p');
    sectionHeading.className = 'agent-section-title';
    sectionHeading.textContent = 'RÉCITS DE L’EXPOSITION';
    summary.append(sectionHeading);
    data.exhibition.sections.forEach(section => {
      const sectionTitle = document.createElement('p');
      sectionTitle.className = 'agent-section-title';
      sectionTitle.textContent = section.title;
      const narrative = document.createElement('p');
      narrative.className = 'agent-result-copy';
      narrative.textContent = section.narrative;
      summary.append(sectionTitle, narrative);
    });
  }

  agentResults.replaceChildren(
    summary,
    ...data.agents.map(agent => appendAgentCard(agent, providerRateLimited, artifactsById)),
  );
  agentResults.hidden = false;

  if (data.partial) {
    const artifactCount = (data.artifacts || []).length;
    agentRunStatus.dataset.tone = artifactCount ? 'warning' : 'error';
    const interruption = providerRateLimited
      ? 'Le fournisseur IA a limité les requêtes.'
      : 'L’analyse s’est arrêtée avant la curation complète.';
    agentRunStatus.textContent = artifactCount
      ? `${interruption} ${completedSpecialists}/5 spécialistes ont terminé; ${artifactCount} article(s) sauvegardé(s) restent visibles dans les salles.`
      : `${interruption} Aucun article partiel n’a été sauvegardé; la dernière exposition complète reste disponible.`;
  } else {
    agentRunStatus.dataset.tone = completedSpecialists === 5 ? 'success' : 'warning';
    agentRunStatus.textContent = completedSpecialists === 5
      ? 'Les cinq spécialistes ont terminé. Consultez les statuts de la relecture, de la curation et de la vérification ci-dessous.'
      : `${completedSpecialists}/5 spécialistes ont produit des conclusions sourcées. Les autres n’ont pas pu étayer leurs réponses avec ces archives.`;
  }
}

async function runMuseumAgents() {
  const preset = exhibitPresets[Number(agentTheme.value)];
  if (!preset) {
    agentRunStatus.hidden = false;
    agentRunStatus.dataset.tone = 'error';
    agentRunStatus.textContent = 'Aucun récit sélectionné. Rechargez la page pour vérifier les archives.';
    return;
  }

  runAgentsButton.disabled = true;
  runAgentsButton.textContent = 'Les agents analysent les archives…';
  agentRunStatus.hidden = false;
  agentRunStatus.dataset.tone = '';
  agentRunStatus.textContent = 'Les spécialistes recherchent chacun dans les archives selon leur domaine, puis le musée lance la relecture, la curation et la vérification. Cela peut prendre plusieurs minutes.';
  agentResults.replaceChildren();
  agentResults.hidden = true;

  try {
    const payload = await window.MuseumPipeline.run({
      query: preset.title,
      chunks: preset.chunks,
      country: 'Tunisia',
      use_rag: true,
    }, () => {
      agentRunStatus.textContent = 'Une exposition est déjà en cours. Le musée la suit et affichera ses résultats dès qu’elle sera terminée.';
    });
    renderAgentRun(payload, preset);
  } catch (error) {
    agentRunStatus.dataset.tone = 'error';
    const message = error.message || '';
    agentRunStatus.textContent = /provider rate limit|rate limit|429/i.test(message)
      ? 'Le fournisseur IA a atteint sa limite de requêtes. La dernière exposition validée reste affichée; réessayez lorsque la limite sera levée.'
      : message || 'L’analyse a échoué. Vérifiez la configuration IA et réessayez.';
  } finally {
    runAgentsButton.disabled = false;
    runAgentsButton.innerHTML = 'Lancer les huit agents <span aria-hidden="true">↗</span>';
  }
}

async function restoreExistingExhibition() {
  runAgentsButton.disabled = true;
  try {
    const data = await window.MuseumPipeline.loadExisting(progress => {
      agentRunStatus.hidden = false;
      agentRunStatus.textContent = 'Une exposition est en cours. Le musée la suit et affichera ses résultats dès qu’elle sera terminée.';
    });
    if (data) {
      renderAgentRun(data, { title: data.query || data.exhibition?.title || 'Dernière exposition' });
    }
  } catch (error) {
    agentRunStatus.hidden = false;
    agentRunStatus.dataset.tone = 'error';
    agentRunStatus.textContent = error.message || 'Impossible de charger les résultats du musée.';
  } finally {
    runAgentsButton.disabled = exhibitPresets.length === 0;
  }
}

function canWalkTo(position) {
  if (Math.hypot(position.x, position.z) <= 5.3) return true;
  for (const group of roomGroups) {
    const local = group.worldToLocal(new THREE.Vector3(position.x, 0, position.z));
    const insideGallery = Math.abs(local.x) < 5.35 && local.z < -0.16 && local.z > -14.45;
    const inDoorway = Math.abs(local.x) < 2.02 && local.z >= -0.16 && local.z < 1.25;
    if (insideGallery || inDoorway) return true;
  }
  return false;
}

function updateMovement(delta) {
  if (!walkMode) return;
  const forward = Number(heldKeys.has('KeyW') || heldKeys.has('ArrowUp'))
    - Number(heldKeys.has('KeyS') || heldKeys.has('ArrowDown'));
  const sideways = Number(heldKeys.has('KeyD') || heldKeys.has('ArrowRight'))
    - Number(heldKeys.has('KeyA') || heldKeys.has('ArrowLeft'));
  if (!forward && !sideways) return;

  const speed = heldKeys.has('ShiftLeft') || heldKeys.has('ShiftRight') ? 5.2 : 3.1;
  const direction = new THREE.Vector3();
  camera.getWorldDirection(direction);
  direction.y = 0;
  direction.normalize();
  const right = new THREE.Vector3().crossVectors(direction, camera.up).normalize().negate();
  const velocity = direction.multiplyScalar(forward).add(right.multiplyScalar(sideways));
  if (velocity.lengthSq() > 1) velocity.normalize();
  velocity.multiplyScalar(speed * delta);

  const nextX = camera.position.clone();
  nextX.x += velocity.x;
  if (canWalkTo(nextX)) camera.position.x = nextX.x;
  const nextZ = camera.position.clone();
  nextZ.z += velocity.z;
  if (canWalkTo(nextZ)) camera.position.z = nextZ.z;
}

function updateHover(event) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const nextTarget = raycaster.intersectObjects(interactiveTargets, false)[0]?.object || null;
  if (nextTarget !== hoveredTarget) {
    hoveredTarget = nextTarget;
    canvas.style.cursor = hoveredTarget ? 'pointer' : walkMode ? 'grab' : 'crosshair';
  }
}

function resize() {
  const width = Math.max(1, view.clientWidth);
  const height = Math.max(1, view.clientHeight);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}

function updateMovementHint() {
  movementHint.textContent = isSmallScreen.matches
    ? 'TOUCHEZ LES FLÈCHES POUR BOUGER'
    : 'CLAVIER W A S D POUR MARCHER';
}

function animate() {
  const delta = Math.min(clock.getDelta(), 0.05);
  updateMovement(delta);
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

async function startMuseum() {
  try {
    await loadPresets();
    addCentralRotunda();
    rooms.forEach(addGallery);
    renderRoomNavigation();
    resize();
    renderer.render(scene, camera);
    loadState.hidden = true;
    startButton.disabled = false;
    startButton.addEventListener('click', () => setWalkMode(!walkMode));
    canvas.addEventListener('pointermove', event => {
      if (event.pointerId === lookPointer) {
        const deltaX = event.clientX - previousTouchPosition.x;
        const deltaY = event.clientY - previousTouchPosition.y;
        if (Math.abs(deltaX) + Math.abs(deltaY) > 1) didLookDrag = true;
        camera.rotation.y -= deltaX * 0.004;
        camera.rotation.x = THREE.MathUtils.clamp(
          camera.rotation.x - deltaY * 0.003,
          -Math.PI / 2.2,
          Math.PI / 2.2,
        );
        previousTouchPosition = { x: event.clientX, y: event.clientY };
      } else {
        updateHover(event);
      }
    });
    canvas.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      lookPointer = event.pointerId;
      previousTouchPosition = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    });
    const releaseLook = event => {
      if (event.pointerId === lookPointer) {
        lookPointer = null;
        window.setTimeout(() => { didLookDrag = false; }, 200);
      }
    };
    canvas.addEventListener('pointerup', releaseLook);
    canvas.addEventListener('pointercancel', releaseLook);
    canvas.addEventListener('click', event => {
      if (didLookDrag) {
        didLookDrag = false;
        return;
      }
      updateHover(event);
      if (hoveredTarget) describeExhibit(hoveredTarget);
    });
    window.addEventListener('resize', resize);
    isSmallScreen.addEventListener('change', updateMovementHint);
    updateMovementHint();
    runAgentsButton.addEventListener('click', runMuseumAgents);
    window.addEventListener('keydown', event => {
      if (walkMode && ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight'].includes(event.code)) {
        heldKeys.add(event.code);
        event.preventDefault();
      }
      if (event.code === 'Escape') setWalkMode(false);
    });
    window.addEventListener('keyup', event => heldKeys.delete(event.code));
    window.addEventListener('blur', () => heldKeys.clear());
    touchControls.querySelectorAll('[data-move]').forEach(button => {
      const movementKeys = { forward: 'KeyW', back: 'KeyS', left: 'KeyA', right: 'KeyD' };
      const key = movementKeys[button.dataset.move];
      button.addEventListener('pointerdown', event => {
        event.preventDefault();
        if (event.isTrusted) button.setPointerCapture(event.pointerId);
        heldKeys.add(key);
      });
      const release = () => heldKeys.delete(key);
      button.addEventListener('pointerup', release);
      button.addEventListener('pointercancel', release);
      button.addEventListener('lostpointercapture', release);
    });
    animate();
    restoreExistingExhibition();
  } catch (error) {
    console.error('The 3D museum could not be initialized:', error);
    loadState.classList.add('is-error');
    loadState.querySelector('strong').textContent = 'La visite 3D ne peut pas démarrer.';
    loadState.querySelector('span:last-child').textContent = 'Vérifiez votre connexion Internet et que votre navigateur autorise WebGL, puis rechargez cette page.';
  }
}

startMuseum();
