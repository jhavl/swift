import React, { useRef, useEffect } from 'react'
import { extend, useThree, useFrame, ReactThreeFiber } from 'react-three-fiber'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'

extend({ OrbitControls })

declare global {
    // eslint-disable-next-line @typescript-eslint/no-namespace
    namespace JSX {
        interface IntrinsicElements {
            orbitControls: ReactThreeFiber.Object3DNode<
                OrbitControls,
                typeof OrbitControls
            >
        }
    }
}

const Controls = (): JSX.Element => {
    const {
        camera,
        gl: { domElement },
    } = useThree()

    // Ref to the controls, so that we can update them on every frame using useFrame
    const controls = useRef<OrbitControls>()

    useFrame(() => controls.current.update())

    useEffect(() => {
        controls.current.target = new THREE.Vector3(0, 0, 0.2)
    }, [])

    return <orbitControls ref={controls} args={[camera, domElement]} />
}

export default Controls
