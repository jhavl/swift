
const tr = require('three')
const zerorpc = require("zerorpc");

import {OrbitControls} from 'app:orbit-controls.mjs'
import { STLLoader } from 'app:stl-loader.mjs'
import {Robot, FPS, SimTime} from 'app:lib.mjs'

let fps = new FPS(document.getElementById('fps'));
let sim_time = new SimTime(document.getElementById('sim-time'));
let time = Date.now();
let t = Date.now();

tr.Object3D.DefaultUp.set(0, 0, 1);

var camera, scene, renderer, controls;
var geometry, material, mesh;

// Array of all the robots in the scene
let agents = [];
let first_step = 0;

init()
animate();
window.addEventListener('resize', on_resize, false);

function init() {

	camera = new tr.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.01, 10);
	scene = new tr.Scene();


	renderer = new tr.WebGLRenderer( {antialias: true });
	renderer.setSize(window.innerWidth, window.innerHeight);
	renderer.shadowMap.enabled = true;
	let div = document.getElementById( 'canvas' );
	document.body.appendChild(div);
	div.appendChild(renderer.domElement)
	controls = new OrbitControls( camera, renderer.domElement );

	// Set up camera position
	camera.position.set(0.3, 0.9, 0.2);
	camera.lookAt(new tr.Vector3(0,0,0))
	camera.rotateZ(3.14)
	controls.update()

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

	// var loader = new STLLoader();
	// loader.load( './models/stl/ascii/puma560/link0.stl', function ( geometry ) {

	// 	var material = new tr.MeshPhongMaterial( { color: 0xff5533, specular: 0x111111, shininess: 200 } );
	// 	var mesh = new tr.Mesh( geometry, material );

	// 	mesh.position.set(0, 0, 0.6);
	// 	// mesh.rotation.set( 0, - Math.PI / 2, 0 );
	// 	// mesh.scale.set(1, 1, 1);

	// 	mesh.castShadow = true;
	// 	mesh.receiveShadow = true;

	// 	scene.add( mesh );
	// });

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

	let delta = Date.now() - time;
	time = Date.now();

	fps.frame(delta);

	if (first_step) {
		sim_time.display()
	}
}

function step_sim() {
	if (!first_step) {
		first_step = 1;
		sim_time.time = Date.now();
	}
	let delta = sim_time.delta();

	for (let i = 0; i < agents.length; i++) {
		agents[i].apply_q(delta)
	}
}





let server = new zerorpc.Server({
    robot: function(model, reply) {
		let robot = new Robot(scene, model);
		let id = agents.length
		agents.push(robot)
        reply(null, id);
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
		reply(null, 1)
	},
	step: function(step, reply) {
		step_sim();
		reply(null, 1)
	},
	get_q: function(id, reply) {
		reply(null, agents[id].q)
	}
});

server.bind("tcp://0.0.0.0:4242");





