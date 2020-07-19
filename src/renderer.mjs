
const tr = require('three')
const zerorpc = require("zerorpc");
const Stats = require('stats-js')

import {OrbitControls} from 'app:orbit-controls.mjs'
import { STLLoader } from 'app:stl-loader.mjs'
import {Robot, Cylinder} from 'app:lib.mjs'


tr.Object3D.DefaultUp.set(0, 0, 1);

var camera, scene, renderer, controls;
var geometry, material, mesh;
var stats;
// let cyl
let robot;
let q;



















init()
animate();
window.addEventListener('resize', on_resize, false);

function init() {


	camera = new tr.PerspectiveCamera( 70, window.innerWidth / window.innerHeight, 0.01, 10 );
	scene = new tr.Scene();

	// // Test object
	// geometry = new tr.BoxGeometry( 0.2, 0.2, 0.2 );
	// material = new tr.MeshNormalMaterial();
	// mesh = new tr.Mesh( geometry, material );
	// mesh.translateZ(0.5)
	// scene.add( mesh );

	renderer = new tr.WebGLRenderer( { antialias: true } );
	renderer.setSize( window.innerWidth, window.innerHeight );
	renderer.shadowMap.enabled = true;
	let div = document.getElementById( 'canvas' );
	document.body.appendChild(div);
	div.appendChild(renderer.domElement)
	controls = new OrbitControls( camera, renderer.domElement );

	// Set up camera position
	camera.position.set( 0.3, 0.9, 0.9 );
	camera.lookAt(new tr.Vector3(0,0,0))
	camera.rotateZ(3.14)
	controls.update()

	// scene.background = new tr.Color(0x72645b);
	scene.background = new tr.Color(0x787878);
	scene.fog = new tr.Fog(0x787878, 2, 15 );

	// Construct a ground plane
	// var geometry = new tr.PlaneGeometry( 5, 5, 32 );
	// var material = new tr.MeshLambertMaterial( {color: 0xededed, side: tr.DoubleSide} );
	// var plane = new tr.Mesh( geometry, material );
	var plane = new tr.Mesh(
		new tr.PlaneBufferGeometry( 40, 40 ),
		new tr.MeshPhongMaterial( { color: 0x4B4B4B, specular: 0x101010 } )
	);
	plane.receiveShadow = true;
	scene.add( plane );

	// // Add a soft white light
	// var light = new tr.AmbientLight( 0x7d7d7d );
	// scene.add( light );

	// Lights

	scene.add( new tr.HemisphereLight( 0x443333, 0x111122 ) );

	addShadowedLight( 1, 1, 1, 0xffffff, 1.35 );
	addShadowedLight( 0.5, 1, - 1, 0xffaa00, 1 );

	// stats

	stats = new Stats();
	stats.showPanel(0);
	// container.appendChild(stats.dom);

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

	// var geometry = new tr.CylinderGeometry( 0.07, 0.07, 0.44, 128 );
	// var material = new tr.MeshBasicMaterial( {color: 0xffff00} );
	// var cylinder = new tr.Mesh( geometry, material );
	// cylinder.position.set(0, 0, 0)
	// scene.add( cylinder );
	// cyl = new Cylinder(scene, 0.44);
	// robot = new Robot(scene);
}

function animate() {

	requestAnimationFrame(animate);

	// cyl.pivot.rotateY(0.01)

	// mesh.rotation.x += 0.01;
    // mesh.rotation.y += 0.02;
    
    // controls.update();

	renderer.render( scene, camera );
	stats.update();
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


var server = new zerorpc.Server({
    robot: function(loc, reply) {
		// console.log(loc)
		robot = new Robot(scene, loc);
        reply(null, "Robot made");
	},
	q: function(q, reply) {
		robot.q(q);
		reply(null, "Joints updated");
	}
});

server.bind("tcp://0.0.0.0:4242");


