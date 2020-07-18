
const tr = require('three')

class Robot{
    constructor(scene, loc) {
        this.robot = new tr.Group()
        this.L = []
        scene.add(this.robot)
        this.robot.rotateX(Math.PI/2)

        this.n = loc.length

        // let t = loc[0]
        // t[4] = 0.2
        // t[3] = 0
        // // t[5] = 0.4
        // // t[2] = 0.4/

        // let l1 = new LinkMDH(scene, t, this.robot)

        // let v = loc[0]
        // v[4] = 0.2
        // v[3] = 0.4
        // // v[5] = 0.4
        // // v[2] = -0.4

        // let l2 = new LinkMDH(scene, v, l1.pe)

        // l1



        let prev = this.robot
        for (let i = 0; i < this.n; i++) {
            this.L.push(new LinkMDH(scene, loc[i], prev))
            prev = this.L[i].pe
        }



        console.log(loc)
    }

    q(q) {
        for (let i = 0; i < this.n; i++) {
            this.L[i].lz.ps.rotateY(q[i])
            // prev = this.L[i].pe
        }
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

        console.log(Rx)
        this.ps.rotateX(Rx)
        this.lz.ps.rotateY(Rz)


    }
}

class Cylinder{
	constructor(length, prev) {
        this.length = length
		this.geometry = new tr.CylinderGeometry( 0.025, 0.025, length, 128 );
		this.material = new tr.MeshPhongMaterial( { color: 0xff5533, specular: 0x111111, shininess: 200 } );
        this.link = new tr.Mesh( this.geometry, this.material );
        this.link.castShadow = true;
		this.link.receiveShadow = true;
        
        this.ps = new tr.Group();
        this.pe = new tr.Group();

        if (length !== 0) {
            console.log(prev.position)
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

// Rotate an object around an arbitrary axis in object space
var rotObjectMatrix;
function rotateAroundObjectAxis(object, axis, radians) {
    rotObjectMatrix = new THREE.Matrix4();
    rotObjectMatrix.makeRotationAxis(axis.normalize(), radians);

    // old code for Three.JS pre r54:
    // object.matrix.multiplySelf(rotObjectMatrix);      // post-multiply
    // new code for Three.JS r55+:
    object.matrix.multiply(rotObjectMatrix);

    // old code for Three.js pre r49:
    // object.rotation.getRotationFromMatrix(object.matrix, object.scale);
    // old code for Three.js r50-r58:
    // object.rotation.setEulerFromRotationMatrix(object.matrix);
    // new code for Three.js r59+:
    object.rotation.setFromRotationMatrix(object.matrix);
}

var rotWorldMatrix;
// Rotate an object around an arbitrary axis in world space       
function rotateAroundWorldAxis(object, axis, radians) {
    rotWorldMatrix = new THREE.Matrix4();
    rotWorldMatrix.makeRotationAxis(axis.normalize(), radians);

    // old code for Three.JS pre r54:
    //  rotWorldMatrix.multiply(object.matrix);
    // new code for Three.JS r55+:
    rotWorldMatrix.multiply(object.matrix);                // pre-multiply

    object.matrix = rotWorldMatrix;

    // old code for Three.js pre r49:
    // object.rotation.getRotationFromMatrix(object.matrix, object.scale);
    // old code for Three.js pre r59:
    // object.rotation.setEulerFromRotationMatrix(object.matrix);
    // code for r59+:
    object.rotation.setFromRotationMatrix(object.matrix);
}











export {Robot, Cylinder};