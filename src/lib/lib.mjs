
const tr = require('three')
import { ColladaLoader } from 'app:tlib/collada-loader.mjs'

const loader = new ColladaLoader();

function sleep(milliseconds) {
    const date = Date.now();
    let currentDate = null;
    do {
      currentDate = Date.now();
    } while (currentDate - date < milliseconds);
  }

function load(ob, scene, t, q) {
    return loader.load(ob.filename, function(collada) {

        let dae = collada.scene;
        dae.position.set(t[0], t[1], t[2]);

        let quat = new tr.Quaternion(q[1], q[2], q[3], q[0]);
        dae.setRotationFromQuaternion(quat);

        for (let i = 0; i < dae.children.length; i++) {
            if (dae.children[i] instanceof tr.Mesh) {
                dae.children[i].castShadow = true;
            } else if (dae.children[i] instanceof tr.PointLight) {
                dae.children[i].visible = false;
            }
        }

        scene.add(dae)
        ob['dae'] = dae
        ob['loaded'] = true
    });
}



class Robot{
    constructor(scene, ob) {

        this.ob = ob

        for (let i = 0; i < ob.M; i++) {
            for (let j = 0; j < ob.links[i].geometry.length; j++) {
                // console.log(ob.link[i].geometry[j].filename)
                load(ob.links[i].geometry[j], scene, ob.links[i].t, ob.links[i].q)
            }
        }

        // this.robot = new tr.Group()
        // this.L = []
        // scene.add(this.robot)
        // this.robot.rotateX(Math.PI/2)

        // this.model = ob[1]
        // this.n = this.model.length
        // this.qd = new Array(this.n).fill(0);
        // this.q = new Array(this.n).fill(0);

        // let prev = this.robot
        // for (let i = 0; i < this.n; i++) {
        //     this.L.push(new LinkMDH(scene, this.model[i], prev))
        //     prev = this.L[i].pe
        // }
    }

    set_poses(poses) {
        for (let i = 0; i < this.ob.M; i++) {

            let t = poses.links[i].t
            let q = poses.links[i].q
            let quat = new tr.Quaternion(q[1], q[2], q[3], q[0]);
            // console.log(this.ob.links[i].geometry.length)
            for (let j = 0; j < this.ob.links[i].geometry.length; j++) {
                this.ob.links[i].geometry[j].dae.position.set(t[0], t[1], t[2]);
                this.ob.links[i].geometry[j].dae.setRotationFromQuaternion(quat);
            }
        }
    }

    set_q(q) {
        for (let i = 0; i < this.n; i++) {
            this.q[i] = q[i]
            // this.L[i].lz.ps.rotateY(q[i])
            this.L[i].lz.ps.setRotationFromEuler(new tr.Euler(0, q[i], 0));
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
}

class LinkMDH{
    constructor(scene, li, prev) {

        // alpha
        let Rx = li[5];

        // a
        let Tx = li[4];

        // theta
        let Rz = li[2];

        // d
        let Tz = li[3];

        // let p0 = new tr.Group();
        // p0.position.set(0, 0, 0)
        // scene.add(p0)
        
        this.ps = new tr.Group()
        this.pe = new tr.Group()
        prev.add(this.ps)

        
        this.lx = new Cylinder(Tx, this.ps);
        this.lx.ps.rotateZ(-Math.PI/2)
        this.lx.pe.rotateZ(Math.PI/2)

        // let b = new tr.AxesHelper(0.4);
        // this.lx.link.add(b)

        // this.lx.pe.rotateX(-Math.PI/2)
        this.lz = new Cylinder(Tz, this.lx.pe);

        // let a = new tr.AxesHelper(0.2);


        this.lz.pe.add(this.pe)
        // this.pe.add(a)
        this.joint = new Revolute(this.pe)
        // this.lz.link.add(a)

        this.ps.rotateX(Rx)
        this.lz.ps.rotateY(Rz)


    }
}

class Cylinder{
	constructor(length, prev) {
        this.length = length
		this.geometry = new tr.CylinderGeometry(0.025, 0.025, length, 128);
		// this.material = new tr.MeshPhongMaterial({ 
        //     color: 0xff5533, 
        //     specular: 0x111111, 
        //     shininess: 20, 
        //     side:tr.DoubleSide
        // });
        this.material = new tr.MeshStandardMaterial({
            color: 0xff5533
        })

        this.link = new tr.Mesh(this.geometry, this.material);
        // this.link.castShadow = true;
		// this.link.receiveShadow = true;
        
        this.ps = new tr.Group();
        this.pe = new tr.Group();

        if (length !== 0) {
            this.link.position.set(0, length/2, 0)
            this.pe.position.set(0, length/2, 0)
            prev.add(this.ps)
            this.ps.add(this.link)
            this.link.add(this.pe)
        } else {
            prev.add(this.ps)
            this.ps.add(this.pe)
        }
    }
}

class Revolute{
    constructor(prev) {
        length = 0.07
        this.geometry = new tr.CylinderGeometry(0.003, 0.003, length, 12);
        this.material = new tr.MeshPhongMaterial( { color: 0xf542ec, specular: 0x111111, shininess: 200 } );
        this.joint = new tr.Mesh(this.geometry, this.material);
        this.joint.position.set(0, length/2, 0)
        prev.add(this.joint)
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
        this.s_time = performance.now();
        this.last_time = performance.now();

        this.c_time = 0.0;
        this.last_c_time = performance.now();
    }

	delta(paused) {
        let delta = performance.now() - this.last_time;
        this.last_time = performance.now();
        
        if (!paused) {
            this.c_time += delta;
        }

        return delta
    }
    
    display() {
        // let t = performance.now() - this.s_time;
        let t = this.c_time
        let s = Math.floor(t / 1000);
        let m = Math.floor(s / 60);
        let ms = t % 1000;
        ms = Math.round(ms)

        s = s % 60;
        // m = m % 60;

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







export {Robot, Cylinder, FPS, SimTime};