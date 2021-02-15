
import { ColladaLoader } from './vendor/examples/jsm/loaders/ColladaLoader.js'
import { STLLoader } from './vendor/examples/jsm/loaders/STLLoader.js'

const daeloader = new ColladaLoader();
const stlloader = new STLLoader();
let nav_div_showing = false;

function sleep(milliseconds) {
    const date = Date.now();
    let currentDate = null;
    do {
      currentDate = Date.now();
    } while (currentDate - date < milliseconds);
  }

function load(ob, scene, color, cb) {
    if (ob.stype === 'mesh') {
        loadMesh(ob, scene, cb);
    } else if (ob.stype === 'box') {
        loadBox(ob, scene, color, cb);
    } else if (ob.stype === 'sphere') {
        loadSphere(ob, scene, color, cb);
    } else if (ob.stype === 'cylinder') {
        loadCylinder(ob, scene, color, cb);
    }
}
    
function loadBox(ob, scene, color, cb) {
    let geometry = new THREE.BoxGeometry( ob.scale[0], ob.scale[1], ob.scale[2] );
    let material = new THREE.MeshStandardMaterial({
        color: color
    })
    let cube = new THREE.Mesh( geometry, material );
    cube.position.set(ob.t[0], ob.t[1], ob.t[2]);
    
    let quat = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
    cube.setRotationFromQuaternion(quat);

    scene.add( cube );
    ob['mesh'] = cube;
    ob['loaded'] = true;
    cb();
}

function loadSphere(ob, scene, color, cb) {
    let geometry = new THREE.SphereGeometry( ob.radius, 64, 64 );
    let material = new THREE.MeshStandardMaterial({
        color: color
    })
    material.transparent = true;
    material.opacity = 0.4;
    let sphere = new THREE.Mesh( geometry, material );
    sphere.position.set(ob.t[0], ob.t[1], ob.t[2]);
    
    let quat = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
    sphere.setRotationFromQuaternion(quat);

    scene.add( sphere );
    ob['mesh'] = sphere;
    ob['loaded'] = true;
    cb();
}

function loadCylinder(ob, scene, color, cb) {
    let geometry = new THREE.CylinderGeometry( ob.radius, ob.radius, ob.length, 32 );
    let material = new THREE.MeshStandardMaterial({
        color: color
    })
    material.transparent = true;
    material.opacity = 0.4;
    let cylinder = new THREE.Mesh( geometry, material );
    cylinder.position.set(ob.t[0], ob.t[1], ob.t[2]);
    
    let quat = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
    cylinder.setRotationFromQuaternion(quat);

    scene.add( cylinder );
    ob['mesh'] = cylinder;
    ob['loaded'] = true;
    cb();
}

function loadMesh(ob, scene, cb) {

    let ext = ob.filename.split('.').pop();

    if (navigator.appVersion.indexOf("Win") != -1) {
        console.log(ob.filename);
        ob.filename = ob.filename.slice(2);
        console.log(ob.filename);
    }

    let addDae = function(collada) {

            let mesh = collada.scene;
            mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);

            let quat = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
            mesh.setRotationFromQuaternion(quat);

            for (let i = 0; i < mesh.children.length; i++) {
                if (mesh.children[i].type === 'Mesh') {
                    mesh.children[i].castShadow = true;
                } else if (mesh.children[i].type === 'PointLight') {
                    mesh.children[i].visible = false;
                }
            }

            scene.add(mesh);
            ob['mesh'] = mesh;
            ob['loaded'] = true;
            cb();
    };

    if (ext == 'dae') {
        let loader = daeloader.load(ob.filename, addDae);
    } else if (ext == 'stl') {
        let loader = stlloader.load(ob.filename, function(geometry) {

            let material = new THREE.MeshPhongMaterial({
                color: new THREE.Color(
                    ob.color[0], ob.color[1], ob.color[2]),
                    specular: 0x111111, shininess: 200
            });

            material.transparent = true;
            material.opacity = ob.color[3];

            let mesh = new THREE.Mesh(geometry, material);

            mesh.scale.set(ob.scale[0], ob.scale[1], ob.scale[2]);
            mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);
            
            let quat_o = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
            mesh.setRotationFromQuaternion(quat_o);
    
            mesh.castShadow = true;
            mesh.receiveShadow = true;
    
            scene.add(mesh);
            ob['mesh'] = mesh;
            ob['loaded'] = true;
            cb();
        });
    }

}


class Robot{
    constructor(scene, ob) {

        this.ob = ob;
        this.promised = 0;
        this.loaded = 0;
        this.model_loaded = 0;

        let cb = () => {
            this.loaded++;
            if (this.loaded === this.promised) {
                this.model_loaded = 1
            }
        }

        for (let i = 0; i < ob.links.length; i++) {
            let color = Math.random() * 0xffffff;

            if (ob.show_robot) {
                for (let j = 0; j < ob.links[i].geometry.length; j++) {
                    this.promised++;
                    load(ob.links[i].geometry[j], scene, color, cb)
                }
            }

            if (ob.show_collision) {
                for (let j = 0; j < ob.links[i].collision.length; j++) {
                    this.promised++;
                    load(ob.links[i].collision[j], scene, color, cb)
                }
            }
        }
    }

    isLoaded() {
        return this.model_loaded;
    }

    set_poses(poses) {
        for (let i = 0; i < this.ob.links.length; i++) {

            if (this.ob.show_robot) {
                for (let j = 0; j < this.ob.links[i].geometry.length; j++) {
                    let t = poses.links[i].geometry[j].t;
                    let q = poses.links[i].geometry[j].q;
                    let quat = new THREE.Quaternion(q[1], q[2], q[3], q[0]);
                    this.ob.links[i].geometry[j].mesh.position.set(t[0], t[1], t[2]);
                    this.ob.links[i].geometry[j].mesh.setRotationFromQuaternion(quat);
                }
            }

            if (this.ob.show_collision) {
                for (let j = 0; j < this.ob.links[i].collision.length; j++) {
                    let t = poses.links[i].collision[j].t;
                    let q = poses.links[i].collision[j].q;
                    let quat = new THREE.Quaternion(q[1], q[2], q[3], q[0]);
                    this.ob.links[i].collision[j].mesh.position.set(t[0], t[1], t[2]);
                    this.ob.links[i].collision[j].mesh.setRotationFromQuaternion(quat);
                }
            }
        }
    }

    set_q(q) {
        for (let i = 0; i < this.n; i++) {
            this.q[i] = q[i]
            // this.L[i].lz.ps.rotateY(q[i])
            this.L[i].lz.ps.setRotationFromEuler(new THREE.Euler(0, q[i], 0));
        }
    }

    set_qd(qd) {
        for (let i = 0; i < this.n; i++) {
            this.qd[i] = qd[i]
        }
    }

    apply_q(delta) {
        let dt = delta / 1000;
        for (let i = 0; i < this.n; i++) {
            this.q[i] += this.qd[i] * dt;
        }
        this.set_q(this.q);
    }

    remove(scene) {
        for (let i = 0; i < this.ob.links.length; i++) {

            if (this.ob.show_robot) {
                for (let j = 0; j < this.ob.links[i].geometry.length; j++) {
                    try {
                        this.ob.links[i].geometry[j].mesh.material.dispose();
                        this.ob.links[i].geometry[j].mesh.geometry.dispose();
                    } catch {};

                    scene.remove(this.ob.links[i].geometry[j].mesh);
                }
            }

            if (this.ob.show_collision) {
                for (let j = 0; j < this.ob.links[i].collision.length; j++) {
                    try {
                        this.ob.links[i].collision[j].mesh.material.dispose();
                        this.ob.links[i].collision[j].mesh.geometry.dispose();
                    } catch {};

                    scene.remove(this.ob.links[i].collision[j].mesh);
                }
            }
        }
    }
}


class Shape{
    constructor(scene, ob) {
        this.ob = ob
        let color = Math.random() * 0xffffff;
        this.loaded = 0;

        let cb = () => {
            this.loaded = 1;
        }

        load(ob, scene, color, cb);
    }

    set_poses(pose) {
        let t = pose.t;
        let q = pose.q;
        let quat = new THREE.Quaternion(q[1], q[2], q[3], q[0]);
        this.ob.mesh.position.set(t[0], t[1], t[2]);
        this.ob.mesh.setRotationFromQuaternion(quat);
    }

    remove(scene) {
        this.ob.mesh.geometry.dispose();
        this.ob.mesh.material.dispose();
        scene.remove(this.ob.mesh);
    }
}


class FPS {
	constructor(div) {
		this.fps = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        this.i = 0
        this.time = performance.now();
        
        this.div = div
	}

	frame() {
        let delta = performance.now() - this.time;
        this.time = performance.now();


		this.fps[this.i] = 1000/delta;
        this.i++;
        if (this.i >= 10) {
            this.i = 0;
        }
		let total = 0;

		for (let j = 0; j < 10; j++) {
			total += this.fps[j];
        }

        let fps = Math.round(total / 10)
        
        let fps_str = `${fps} fps`;
        this.div.innerHTML = fps_str;
	}
}


class SimTime {
	constructor(div) {
        this.div = div
    }
    
    display(t) {
        let s = Math.floor(t);
        let m = Math.floor(s / 60);
        let ms = (t * 1000) % 1000;
        ms = Math.round(ms)

        s = s % 60;

        if (s < 10) {
            s = "0" + s;
        }

        if (m < 10) {
            m = "0" + m
        }

        if (ms < 10) {
            ms *= 100;
        } else if (ms < 100) {
            ms *= 10;
        }

        if (ms === 0) {
            ms = "000"
        }

        let t_str = `${m}:${s}.${ms}`;
        this.div.innerHTML = t_str;
    }
}

function show_nav_div() {
    let div = document.getElementById('sidenav');
    div.style.display = 'block';
}

function update_slider(range_slider, slider_val, unit) {
    slider_val.innerHTML = range_slider.value + ' ' + unit
}

function slider(
    id, min=0, max=100, step=10, value=0,
    desc='', unit='', custom_elements={}) {

    if (!nav_div_showing) {
        show_nav_div();
    }

    let ml = `
        <div class="slider-div" id="` + id + `">
            <p class="slider-p" id="` + id + `">
                ` + desc + `
            </p>
            <input type="range" value="` + value + `" step="` + step + `" min="` + min + `" max="` + max + `" class='slider' id="slider` + id + `">

            <div class="slider-val-div" id="` + id + `">
                <p class="slider-vals slider-min" id="min` + id + `">
                    0
                </p>
                <p class="slider-vals slider-val" id="val` + id + `">
                    0
                </p>
                <p class="slider-vals slider-max" id="max` + id + `">
                    100
                </p>
            </div>
        </div>
    `;

    let div = document.getElementById('sidenav');
    div.insertAdjacentHTML('beforeend', ml);

    let range_slider = document.getElementById('slider' + id);
    let slider_val = document.getElementById('val' + id);
    let smin = document.getElementById('min' + id);
    let smax = document.getElementById('max' + id);

    range_slider.value = value;
    slider_val.innerHTML = range_slider.value + unit;
    smin.innerHTML = min;
    smax.innerHTML = max;

    range_slider.addEventListener('input', function () {
        slider_val.innerHTML = range_slider.value + unit;
        custom_elements[id] = true;
    }, true);

    return {id: false};
}






export {Robot, Shape, FPS, SimTime, slider};
