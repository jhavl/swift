THREE.Object3D.DefaultUp.set(0, 0, 1);
const tr = THREE;
const zerorpc = require("zerorpc");
const fs = require('fs');
// import {  } from 'app:../node_modules/ccapture.js/build/CCapture.all.min.js';
// import {CCapture} from 'app:../node_modules/ccapture.js/build/CCapture.all.min.js' 
// const HoloPlay = require("holoplay");

import {OrbitControls} from 'app:tlib/orbit-controls.mjs'
import { STLLoader } from 'app:tlib/stl-loader.mjs'
import {Robot, FPS, SimTime} from 'app:lib/lib.mjs'

let fps = new FPS(document.getElementById('fps'));
let sim_time = new SimTime(document.getElementById('sim-time'));
let heartbeat = performance.now() - 100;
let paused, prev_state = true;

var camera, scene, renderer, controls;

// Array of all the robots in the scene
let agents = [];
let first_step = 0;

// scene recorder
let rec = null

setInterval(rt_heartbeat, 10)
init()
animate();
window.addEventListener('resize', on_resize, false);


function init() {
// 
	camera = new tr.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.01, 10);
	// camera = new HoloPlay.Camera();
	
	scene = new tr.Scene();
	// tr.Object3D.DefaultUp.set(0, 0, 1);

	renderer = new tr.WebGLRenderer( {antialias: true });
	// hrenderer = new HoloPlay.Renderer();
	// hrenderer.webglRenderer = renderer;
	// hrenderer.disableFullscreenUi = true;
	// console.log(hrenderer);

	renderer.setSize(window.innerWidth, window.innerHeight);
	renderer.shadowMap.enabled = true;
	let div = document.getElementById( 'canvas' );
	document.body.appendChild(div);
	div.appendChild(renderer.domElement)
	controls = new OrbitControls( camera, renderer.domElement );

	// Set up camera position
	camera.position.set(0.2, 1.2, 0.7);
	controls.target = new tr.Vector3(0, 0, 0.2);
	controls.update();

	// scene.background = new tr.Color(0x72645b);
	scene.background = new tr.Color(0x787878);
	scene.fog = new tr.Fog(0x787878, 2, 15 );

	var plane = new tr.Mesh(
		new tr.PlaneBufferGeometry( 40, 40 ),
		new tr.MeshPhongMaterial( { color: 0x4B4B4B, specular: 0x101010 } )
	);
	plane.receiveShadow = true;
	scene.add( plane );

	// Lights
	scene.add( new tr.HemisphereLight( 0x443333, 0x111122 ) );
	addShadowedLight( 1, 1, 1, 0xffffff, 1.35 );
	addShadowedLight( 0.5, 1, - 1, 0xffaa00, 1 );

	var axesHelper = new tr.AxesHelper( 5 );
	scene.add( axesHelper );

}


function on_resize() {
	camera.aspect = window.innerWidth / window.innerHeight;
	camera.updateProjectionMatrix();
	renderer.setSize(window.innerWidth, window.innerHeight);
}

function addShadowedLight( x, y, z, color, intensity ) {

	var directionalLight = new tr.DirectionalLight( color, intensity );
	directionalLight.position.set( x, y, z );
	scene.add( directionalLight );

	directionalLight.castShadow = true;

	var d = 1;
	directionalLight.shadow.camera.left = - d;
	directionalLight.shadow.camera.right = d;
	directionalLight.shadow.camera.top = d;
	directionalLight.shadow.camera.bottom = - d;

	directionalLight.shadow.camera.near = 1;
	directionalLight.shadow.camera.far = 4;

	directionalLight.shadow.bias = - 0.002;

}



function animate() {

	requestAnimationFrame(animate);

	renderer.render(scene, camera);

	fps.frame();
	sim_time.display()
}

function step_sim() {
	heartbeat = performance.now()
	let delta = sim_time.delta(paused);

	for (let i = 0; i < agents.length; i++) {
		agents[i].apply_q(delta)
	}
}

function rt_heartbeat() {


	let delta = performance.now() - heartbeat;
	if (delta > 100) {
		paused = true;
	} else {
		paused = false;
	}

	if (prev_state !== paused) {
		let play = document.getElementById('play-button')
		let pause = document.getElementById('pause-button')

		if (paused) {
			pause.style.display = "none";
            play.style.display = "block";
		} else {
			play.style.display = "none";
			pause.style.display = "block";
		}
	}
	prev_state = paused;
}


function startRecording(file) {
	let canvas = document.getElementById('canvas').children[0];
	const chunks = []; // here we will store our recorded media chunks (Blobs)

	const blob_reader = new FileReader();
	const storage_stream = require("fs").createWriteStream(file);
	const blobs = [];

	const stream = canvas.captureStream(); // grab our canvas MediaStream

	blob_reader.addEventListener("load", function(ev) {
		storage_stream.write(Buffer.from(ev.currentTarget.result));
		if(blobs.length) {
			ev.currentTarget.readAsArrayBuffer(blobs.shift());
		}
	});

	rec = new MediaRecorder(stream); // init the recorder

	rec.addEventListener("dataavailable", function(ev) {
		if(blob_reader.readyState != 1) {
			blob_reader.readAsArrayBuffer(ev.data);
		} else {
			blobs.push(ev.data);
		}
	});
	
	rec.start();
	// setTimeout(()=>rec.stop(), 3000); // stop recording in 3s
	// console.log('started')
}




// startRecording('file');

let server = new zerorpc.Server({
    robot: function(model, reply) {
		let id = agents.length
		let robot = new Robot(scene, model);
		
		// let id = 1;
		agents.push(robot)
        reply(null, id);
	},
	poses: function(p_ob, reply) {
		let id = p_ob[0];
		let poses = p_ob[1];
		agents[id].set_poses(poses);
		// step_sim();
		// animate();
		reply(null, 1);
	},
	q: function(q_ob, reply) {
		let id = q_ob[0];
		let q = q_ob[1];
		agents[id].set_q(q);
		reply(null, 1);
	},
	qd: function(qd_ob, reply) {
		let id = qd_ob[0];
		let qd = qd_ob[1];
		agents[id].set_qd(qd);
		reply(null, 1);
	},
	step: function(step, reply) {
		step_sim();
		reply(null, 1);
	},
	get_q: function(id, reply) {
		reply(null, agents[id].q)
	},
	record_start: function(file, reply) {
		startRecording(file);
		reply(null, 1);
	},
	record_stop: function(file, reply) {
		rec.stop();
		reply(null, 1);
	}
});

server.bind("tcp://0.0.0.0:4242");





