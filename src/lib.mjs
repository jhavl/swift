
const tr = require('three')

class Robot{
    constructor(scene, loc) {
        this.robot = []
        this.n = loc.length

        let t = loc[0]
        t[4] = 0.2
        new LinkMDH(scene, t)

        // for (let i = 0; i < loc.length; i++) {
        //     new LinkMDH(scene, loc[i])
        // }
        


        // for (let i = 0; i < loc.length; i+=2) {
        //     let lb = loc[i]
        //     let le = loc[i+1]

        //     // console.log(t)

        //     // // x-axis cylinder
        //     // if (t[0][3] !== 0) {
        //     //     new Cylinder(scene, t[0][3], 0, 0, 0, 0)
        //     // }

        //     // // y-axis cylinder
        //     // if (t[1][3] !== 0) {
        //     //     new Cylinder(scene, t[1][3], 0, 0, 0, 1)
        //     // }

        //     // z-axis cylinder
        //     if (le[2][3] !== 0) {
        //         // console.log([2][3])
        //         new Cylinder(scene, le[2][3], lb[0][3], lb[1][3], lb[2][3], 2)
        //     }

        // }


        console.log(loc)
        // let cyl1 = new Cylinder(scene, 0.4, 0, 0, 0)
        
        // let cyl2 = new Cylinder(scene, 0.4, 0, 0, 0.4)
        // let cyl3 = new Cylinder(scene, 0.4, 0, 0, 0.8)
        
        // cyl1.cylinder.add(cyl2.pivot)
        // cyl1.pivot.rotateX(0.6)
    }
}

class LinkMDH{
    constructor(scene, li) {

        // alpha
        let Rx = li[5];

        // a
        let Tx = li[4];

        // theta
        let Rz = li[2];

        // d
        let Tz = li[3];

        let p0 = new tr.Group();
        p0.position.set(0, 0, 0)
        scene.add(p0)

        let lx = new Cylinder(scene, Tx, 0, 0, 0, 0, p0);
        p0.rotateX(Rx)

        let lz = new Cylinder(scene, Tz, 0, 0, 0, 2, lx.pe);

        // lx.pe.add(lz.pe)
        // lx.pivot.rotateY(0.5)





        // if ( !== 0) {

        // } else

        // if (le[0][3] !== 0) {
        //     new Cylinder(scene, le[0][3], lb[0][3], lb[1][3], lb[2][3], 0)
        // }

        // if (le[1][3] !== 0) {
        //     new Cylinder(scene, le[1][3], lb[0][3] + le[0][3], lb[1][3] , lb[2][3], 1)
        // }

        // if (le[2][3] !== 0) {
        //     new Cylinder(scene, le[2][3], lb[0][3], lb[1][3] + le[1][3], lb[2][3], 2)
        // }

        // let a = new Cylinder(scene, 0.4, 0, 0, 0, 1)
        // a.pivot.rotateX(0.6)
        // a.pivot.rotateX(0.6)
        // a.pivot.rotateZ(0.6)

    }
}

class Cylinder{
	constructor(scene, length, x, y, z, axis, prev) {
        this.scene = scene
        this.length = length
		this.geometry = new tr.CylinderGeometry( 0.01, 0.01, length, 128 );
		this.material = new tr.MeshPhongMaterial( { color: 0xff5533, specular: 0x111111, shininess: 200 } );
        this.link = new tr.Mesh( this.geometry, this.material );
        this.link.castShadow = true;
		this.link.receiveShadow = true;
        

        if (axis === 0) {
            console.log(prev.position)
            this.link.position.set(prev.position.x + length/2, prev.position.y, prev.position.z)
            this.pe = new tr.Group();
            this.pe.position.set(prev.position.x, prev.position.y - length/2, prev.position.z)
            this.link.rotateZ(Math.PI/2)
        } else if (axis === 1) {
            // this.link.position.set(x, y  + length/2, z)
            this.link.rotateY(Math.PI/2)
            // this.ps = new tr.Group(x, y + length/2, z);
            this.pe = new tr.Group(x, y - length/2, z);
        } else if (axis == 2) {
            this.link.position.set(prev.position.x, prev.position.y, prev.position.z + length/2)
            this.link.rotateX(Math.PI/2)
            // this.ps = new tr.Group();
            // this.ps.position.set(x, y, z)
            this.pe = new tr.Group();
            // this.pe.position.set(x, y, z + length)
        }

        prev.add(this.link)
        this.link.add(this.pe)
	}

}

export {Robot, Cylinder};