import React, { useEffect, useState, useRef, Suspense, lazy } from 'react'

import { useThree, useFrame } from 'react-three-fiber'
import * as THREE from 'three'
THREE.Object3D.DefaultUp.set(0, 0, 1)
const Loader = lazy(() => import('./Loader'))

export const Plane: React.FC = (): JSX.Element => {
    const { scene } = useThree()

    scene.background = new THREE.Color(0x787878)
    scene.fog = new THREE.Fog(0x787878, 50, 60)

    return (
        <mesh receiveShadow={true}>
            <planeBufferGeometry args={[200, 200]} />
            <meshPhongMaterial color={0x4b4b4b} specular={0x101010} />
        </mesh>
    )
}

export interface IShadowedLightProps {
    x: number
    y: number
    z: number
    color: number
    intensity: number
}

export const ShadowedLight: React.FC<IShadowedLightProps> = (
    props: IShadowedLightProps
): JSX.Element => {
    const light = useRef<THREE.DirectionalLight>()
    // const d = 1

    // useEffect(() => {
    // light.current.shadow.camera.left = -d
    // light.current.shadow.camera.right = d
    // light.current.shadow.camera.top = d
    // light.current.shadow.camera.bottom = -d
    // light.current.shadow.camera.near = 0
    // light.current.shadow.camera.far = 40
    // light.current.shadow.bias = -0.002
    // }, [])

    return (
        <directionalLight
            ref={light}
            color={props.color}
            intensity={props.intensity}
            position={[props.x, props.y, props.z]}
            castShadow={true}
        />
    )
}

export interface ICameraProps {
    setDefault: boolean
    fpsCallBack: any
}

export const Camera = (props: ICameraProps): JSX.Element => {
    const { viewport, setDefaultCamera } = useThree()

    const { width, height } = viewport

    const camera = useRef<THREE.PerspectiveCamera>()

    useEffect(() => {
        if (props.setDefault) {
            setDefaultCamera(camera.current)
        }
    })

    useFrame((state, delta) => {
        props.fpsCallBack(1.0 / delta)
    })

    return (
        <perspectiveCamera
            ref={camera}
            position={[0.2, 1.2, 0.7]}
            near={0.01}
            far={100}
            fov={70}
            aspect={height / width}
        />
    )
}

const PrimativeShapes = (props: IShapeProps): JSX.Element => {
    switch (props.stype) {
        case 'box':
            return <boxBufferGeometry args={props.scale} />
            break

        case 'sphere':
            return <sphereBufferGeometry args={[props.radius, 64, 64]} />
            break

        case 'cylinder':
            return (
                <cylinderBufferGeometry
                    args={[props.radius, props.radius, props.length, 32]}
                />
            )
            break

        default:
            return <boxBufferGeometry args={props.scale} />
    }
}

export interface IShapeProps {
    stype: string
    scale?: number[]
    filename?: string
    radius?: number
    length?: number
    q?: number[]
    t?: number[]
    v?: number[]
    color?: number
    opacity?: number
    display?: boolean
}

const BasicShape = (props: IShapeProps): JSX.Element => {
    const shape = useRef<THREE.mesh>()
    // useEffect(() => {
    //     if (props.q) {
    //         console.log(props.q)
    //         // const q = new THREE.Quaternion(
    //         //     props.q[1],
    //         //     props.q[2],
    //         //     props.q[3],
    //         //     props.q[0]
    //         // )
    //         // shape.current.setRotationFromQuaternion(q)
    //         // console.log(shape)

    //         // shape.current.quaternion.set(
    //         //     props.q[1],
    //         //     props.q[2],
    //         //     props.q[3],
    //         //     props.q[0]
    //         // )
    //     }
    // }, [])

    // useFrame(() => {
    //     if (shape.current) {
    //         console.log(shape.current.up)
    //     } else {
    //         console.log(shape)
    //     }
    //     // console.log(shape.current.DefaultUp)
    // })

    return (
        <mesh
            ref={shape}
            position={props.t}
            quaternion={props.q}
            castShadow={true}
            name={'loaded'}
        >
            <PrimativeShapes {...props} />
            <meshStandardMaterial
                transparent={props.opacity ? true : false}
                color={props.color ? props.color : 'hotpink'}
                opacity={props.opacity ? props.opacity : 1.0}
            />
        </mesh>
    )
}

const MeshShape = (props: IShapeProps): JSX.Element => {
    const [hasMounted, setHasMounted] = useState(false)

    useEffect(() => {
        setHasMounted(true)

        // const q = new THREE.Quaternion(
        //     props.q[1],
        //     props.q[2],
        //     props.q[3],
        //     props.q[0]
        // )
        // shape.current.setRotationFromQuaternion(q)
        // console.log(shape)
    }, [])

    return (
        <>
            {hasMounted && (
                <Suspense
                    fallback={
                        <BasicShape
                            stype={'box'}
                            scale={[0.1, 0.1, 0.1]}
                            t={props.t}
                            // q={props.q}
                            opacity={0.1}
                            color={0xffffff}
                        />
                    }
                >
                    <Loader {...props} />
                </Suspense>
            )}
        </>
    )
}

export const Shape = (props: IShapeProps): JSX.Element => {
    if (props.display === false) {
        return <></>
    }

    switch (props.stype) {
        case 'mesh':
            return <MeshShape {...props} />
            break

        case 'box':
        case 'cylinder':
        case 'sphere':
        default:
            return <BasicShape {...props} />
            break
    }
}
