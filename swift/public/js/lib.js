
import { ColladaLoader } from './vendor/examples/jsm/loaders/ColladaLoader.js'
import { STLLoader } from './vendor/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from './vendor/examples/jsm/loaders/OBJLoader.js'
import { MTLLoader } from './vendor/examples/jsm/loaders/MTLLoader.js'
import { VRMLoader } from './vendor/examples/jsm/loaders/VRMLoader.js'
import { PCDLoader } from './vendor/examples/jsm/loaders/PCDLoader.js'
import { PLYLoader } from './vendor/examples/jsm/loaders/PLYLoader.js'
import { GLTFLoader } from './vendor/examples/jsm/loaders/GLTFLoader.js'

const daeloader = new ColladaLoader();
const stlloader = new STLLoader();
const objloader = new OBJLoader();
const mtlloader = new MTLLoader();
const vrmloader = new VRMLoader();
const pcdloader = new PCDLoader();
const plyloader = new PLYLoader();
const gltfloader = new GLTFLoader();

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
        // console.log(ob.filename);
        ob.filename = ob.filename.slice(2);
        // console.log(ob.filename);
    }

    if (ext == 'dae') {
        let loader = daeloader.load(ob.filename, function(collada) {

            let mesh = collada.scene;
            mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);
    
            let quat = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
            mesh.setRotationFromQuaternion(quat);
    
            mesh.traverse( function (child) {
                if ( child.isMesh ) {
                    child.castShadow = true;
                    // child.receiveShadow = true;
                } else if (child.type === 'PointLight') {
                    child.visible = false;
                }
            });

            scene.add(mesh);
            ob['mesh'] = mesh;
            ob['loaded'] = true;
            cb();
        });
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
    } else if (ext == 'obj') {
        let loader =  mtlloader.load(ob.filename.slice(0, ob.filename.length-3) + 'mtl',
            function (materials) {
                materials.preload();

                // let objloader = new THREE.OBJLoader();
                objloader.setMaterials(materials);

                objloader.load(ob.filename,
                    function (object) {
                        console.log(object)

                        object.traverse( function (child) {
                            if ( child.isMesh ) {
                                child.castShadow = true;
                                child.receiveShadow = true;
                            }
                        });
        
                        object.scale.set(ob.scale[0], ob.scale[1], ob.scale[2]);
                        object.position.set(ob.t[0], ob.t[1], ob.t[2]);
                        let quat_o = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
                        object.setRotationFromQuaternion(quat_o);
        
                        scene.add(object);
                        ob['mesh'] = object;
                        ob['loaded'] = true;
                        cb();
                    },
                    function (xhr) {
                        console.log( ( xhr.loaded / xhr.total * 100 ) + '% loaded' );
                    },
                    function (error) {
                        console.log('Error loading obj file');
                        console.log(error);
                    }
                );
            }
        );
    } else if (ext == 'gltf' || ext == 'glb') {
        let loader = gltfloader.load(ob.filename,
            function (object) {

                let mesh = object.scene;

                mesh.traverse( function (child) {
                    if ( child.isMesh ) {
                        child.castShadow = true;
                        child.receiveShadow = true;
                    }
                });

                mesh.scale.set(ob.scale[0], ob.scale[1], ob.scale[2]);
                mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);
                let quat_o = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
                mesh.setRotationFromQuaternion(quat_o);

                scene.add(mesh);
                ob['mesh'] = mesh;
                ob['loaded'] = true;
                cb();
            },
            // called when loading is in progresses
            function ( xhr ) {
                console.log( ( xhr.loaded / xhr.total * 100 ) + '% loaded' );
            },
            // called when loading has errors
            function ( error ) {
                console.log('Error loading GLTF file');
                console.log(error);
            }
        );
    } else if (ext == 'ply') {
        let loader = plyloader.load(ob.filename,
            function (geometry) {

                geometry.computeVertexNormals();

                const material = new THREE.MeshPhongMaterial({
                    color: new THREE.Color(
                        ob.color[0], ob.color[1], ob.color[2]),
                        specular: 0x111111, shininess: 200
                });
                const mesh = new THREE.Mesh(geometry, material);

                mesh.castShadow = true;
                mesh.receiveShadow = true;

                mesh.scale.set(ob.scale[0], ob.scale[1], ob.scale[2]);
                mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);
                let quat_o = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
                mesh.setRotationFromQuaternion(quat_o);

                scene.add(mesh);
                ob['mesh'] = mesh;
                ob['loaded'] = true;
                cb();
            },
            // called when loading is in progresses
            function ( xhr ) {
                console.log( ( xhr.loaded / xhr.total * 100 ) + '% loaded' );
            },
            // called when loading has errors
            function ( error ) {
                console.log('Error loading PLY file');
                console.log(error);
            }
        );
    } else if (ext == 'wrl') {
        let loader = vrmloader.load(ob.filename,
            function (mesh) {

                mesh.castShadow = true;
                mesh.receiveShadow = true;

                mesh.scale.set(ob.scale[0], ob.scale[1], ob.scale[2]);
                mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);
                let quat_o = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
                mesh.setRotationFromQuaternion(quat_o);

                scene.add(mesh);
                ob['mesh'] = mesh;
                ob['loaded'] = true;
                cb();
            },
            // called when loading is in progresses
            function ( xhr ) {
                console.log( ( xhr.loaded / xhr.total * 100 ) + '% loaded' );
            },
            // called when loading has errors
            function ( error ) {
                console.log('Error loading VRML file');
                console.log(error);
            }
        );
    } else if (ext == 'pcd') {
        let loader = pcdloader.load(ob.filename,
            function (mesh) {

                mesh.scale.set(ob.scale[0], ob.scale[1], ob.scale[2]);
                mesh.position.set(ob.t[0], ob.t[1], ob.t[2]);
                let quat_o = new THREE.Quaternion(ob.q[1], ob.q[2], ob.q[3], ob.q[0]);
                mesh.setRotationFromQuaternion(quat_o);

                scene.add(mesh);
                ob['mesh'] = mesh;
                ob['loaded'] = true;
                cb();
            },
            // called when loading is in progresses
            function ( xhr ) {
                console.log( ( xhr.loaded / xhr.total * 100 ) + '% loaded' );
            },
            // called when loading has errors
            function ( error ) {
                console.log('Error loading PLY file');
                console.log(error);
            }
        );
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


class Slider {
	constructor(data) {
        if (!nav_div_showing) {
            show_nav_div();
        }
    
        let ml = `
            <div class="slider-div" id="slider-div` + data.id + `">
                <p class="slider-p" id="desc` + data.id + `">
                </p>
                <input type="range" value="0" step="1" min="0" max="100" class='slider' id="slider` + data.id + `">
    
                <div class="slider-val-div" id="slider-val-div` + data.id + `">
                    <p class="slider-vals slider-min" id="min` + data.id + `">
                        0
                    </p>
                    <p class="slider-vals slider-val" id="value` + data.id + `">
                        0
                    </p>
                    <p class="slider-vals slider-max" id="max` + data.id + `">
                        100
                    </p>
                </div>
            </div>
        `;

        let div = document.getElementById('sidenav');
        div.insertAdjacentHTML('beforeend', ml);

        this.slider =  document.getElementById('slider' + data.id),
        this.value =  document.getElementById('value' + data.id),
        this.min =  document.getElementById('min' + data.id),
        this.max =  document.getElementById('max' + data.id)
        this.desc =  document.getElementById('desc' + data.id)
        this.id = data.id;

        this.onInput = () => {
            this.value.innerHTML = this.slider.value + this.unit;
            this.changed = true;
            this.data = this.slider.value;
        }

        this.slider.addEventListener('input', this.onInput, false);

        this.update(data);

        // Common attributes
        this.changed = false;
        this.data = this.slider.value;
    }

    update(data) {
        this.unit = data.unit;
        this.slider.value = data.value;
        this.slider.step = data.step;
        this.slider.min = data.min;
        this.slider.max = data.max;
        this.value.innerHTML = this.slider.value + this.unit;
        this.min.innerHTML = data.min;
        this.max.innerHTML = data.max;
        this.desc.innerHTML = data.desc;

        this.onInput();
    }
}


class Button {
	constructor(data) {
        if (!nav_div_showing) {
            show_nav_div();
        }
    
        let ml = `
            <div class="button-div">
                <button type="button" class="button-button" id="button` + data.id + `"></button>
            </div>
        `;

        let div = document.getElementById('sidenav');
        div.insertAdjacentHTML('beforeend', ml);

        this.button = document.getElementById('button' + data.id),
        this.id = data.id;

        this.onInput = () => {
            this.changed = true;
        }

        this.button.addEventListener('click', this.onInput, false);

        this.update(data);

        // Common attributes
        this.changed = false;
        this.data = 0;
    }

    update(data) {
        this.button.innerHTML = data.desc;
    }
}


class Label {
	constructor(data) {
        if (!nav_div_showing) {
            show_nav_div();
        }
    
        let ml = `
            <div class="label-div">
                <p id="label` + data.id + `"></p>
            </div>
        `;

        let div = document.getElementById('sidenav');
        div.insertAdjacentHTML('beforeend', ml);

        this.label = document.getElementById('label' + data.id);
        this.id = data.id;

        this.update(data);

        // Common attributes
        this.changed = false;
        this.data = 0;
    }

    update(data) {
        this.label.innerHTML = data.desc;
    }
}


class Select {
	constructor(data) {
        if (!nav_div_showing) {
            show_nav_div();
        }
    
        let ml = `
            <div class="select-div">
                <label id="label` + data.id + `" class="select-label"></label>
                <select id="select` + data.id + `" class="select-select">
                </select>
            </div>
        `;

        let div = document.getElementById('sidenav');
        div.insertAdjacentHTML('beforeend', ml);

        this.label = document.getElementById('label' + data.id);
        this.select = document.getElementById('select' + data.id);
        this.id = data.id;

        this.onInput = (e) => {
            this.changed = true;
            this.data = this.select.value;
        }

        this.select.addEventListener('change', this.onInput, false);

        this.update(data);

        // Common attributes
        this.changed = false;
        this.data = 0;
    }

    update(data) {
        this.label.innerHTML = data.desc;

        let sel = '';
        for (let i = 0; i < data.options.length; i++) {
            sel += `<option value="` + i + `">` + data.options[i] + `</option>`
        }
        this.select.innerHTML = sel;
        this.select.value = String(data.value)
    }
}


class Checkbox {
	constructor(data) {
        if (!nav_div_showing) {
            show_nav_div();
        }
    
        let ml = `
            <div class="checkbox-div">
                <p id="label` + data.id + `"></p>
                <div class="checkbox-cont" id="checkboxcont` + data.id + `">
                </div>
            </div>
        `;

        let div = document.getElementById('sidenav');
        div.insertAdjacentHTML('beforeend', ml);

        this.label = document.getElementById('label' + data.id);
        this.checkbox = document.getElementById('checkboxcont' + data.id);
        this.id = data.id;

        this.onChange = (e) => {
            this.data = []
            this.changed = true;
            let checks = this.checkbox.getElementsByTagName('input');

            for (let i = 0; i < checks.length; i++) {
                this.data.push(checks[i].checked);
            }
        }

        this.checkbox.addEventListener('change', this.onChange, false);

        this.update(data);

        // Common attributes
        this.changed = false;
        this.data = [];
    }

    update(data) {
        this.label.innerHTML = data.desc;
        let sel = '';

        for (let i = 0; i < data.options.length; i++) {
            let checked = data.checked[i] ? 'checked' : '';
            sel += `
                <label for="checkbox` + data.id + `">
                    <input type="checkbox" ` + checked + ` id="checkbox` + data.id + i + `" />
                    <span>` + data.options[i] + `</span>
                </label>
            `
            sel += i < data.options.length - 1 ? '<br>' : '';
        }
        this.checkbox.innerHTML = sel;
        
        this.onChange();
    }
}


class Radio {
	constructor(data) {
        if (!nav_div_showing) {
            show_nav_div();
        }
    
        let ml = `
            <div class="radio-div">
                <p id="label` + data.id + `"></p>
                <div class="radio-cont" id="radiocont` + data.id + `">
                </div>
            </div>
        `;

        let opt = `
        <label for="k"><input type="radio" id="k" name="x"/> <span>Label text z</span></label>
        `

        let div = document.getElementById('sidenav');
        div.insertAdjacentHTML('beforeend', ml);

        this.label = document.getElementById('label' + data.id);
        this.radio = document.getElementById('radiocont' + data.id);
        this.id = data.id;

        this.onChange = (e) => {
            this.changed = true;

            let radios = this.radio.getElementsByTagName('input');

            for (let i = 0; i < radios.length; i++) {
                if (radios[i].checked) {
                    this.data = i;
                    break;
                }
            }
        }

        this.radio.addEventListener('change', this.onChange, false);

        this.update(data);

        // Common attributes
        this.changed = false;
        this.data = [];
    }

    update(data) {
        this.label.innerHTML = data.desc;
        let sel = '';

        for (let i = 0; i < data.options.length; i++) {
            let checked = data.checked === i ? 'checked' : '';
            sel += `
                <label for="radio` + data.id + `">
                    <input type="radio" ` + checked + ` id="radio` + data.id + i + `" name="radio` + data.id + `"/>
                    <span>` + data.options[i] + `</span>
                </label>`

            sel += i < data.options.length - 1 ? '<br>' : '';
        }
        this.radio.innerHTML = sel;
        
        this.onChange();
    }
}



export {Robot, Shape, FPS, SimTime, Slider, Button, Label, Select, Checkbox, Radio};
