import * as THREE from 'three'
THREE.Object3D.DefaultUp.set(0, 0, 1)
import React, { useState, useEffect, useRef, lazy, Suspense } from 'react'
import { Canvas } from 'react-three-fiber'

import styles from '../styles/Swift.module.scss'

import {
    Plane,
    ShadowedLight,
    Camera,
    IShapeProps,
    Shape,
} from './SwiftComponents'

const Controls = lazy(() => import('./Controls'))

interface IMeshCollection {
    meshes: IShapeProps[]
}

const MeshCollection = (props: IMeshCollection): JSX.Element => {
    // console.log(props)
    return (
        <group>
            {props.meshes.map((value, i) => {
                return <Shape key={i} {...value} />
            })}
        </group>
    )
}

interface IGroupCollection {
    meshes: IShapeProps[][]
}

const GroupCollection = React.forwardRef<THREE.group, IGroupCollection>(
    (props: IGroupCollection, ref: THREE.group): JSX.Element => {
        return (
            <group ref={ref}>
                {props.meshes.map((value, i) => {
                    return <MeshCollection key={i} meshes={value} />
                })}
            </group>
        )
    }
)

export interface ISwiftProps {
    port: number
}

const Swift: React.FC<ISwiftProps> = (props: ISwiftProps): JSX.Element => {
    const [hasMounted, setHasMounted] = useState(false)
    const shapes = useRef<THREE.group>()
    const ws = useRef<WebSocket>(null)

    const [shapeDesc, setShapeDesc] = useState<IShapeProps[][]>([])

    useEffect(() => {
        setHasMounted(true)
        ws.current = new WebSocket('ws://localhost:' + props.port + '/')
        ws.current.onopen = () => ws.current.send('Connected')
    }, [])

    useEffect(() => {
        ws.current.onmessage = (event) => {
            const eventdata = JSON.parse(event.data)
            const func = eventdata[0]
            const data = eventdata[1]
            switch (func) {
                case 'shape_mounted':
                    {
                        const id = data[0]
                        const len = data[1]

                        try {
                            let loaded = 0
                            shapes.current.children[id].children.forEach(
                                (ob, i) => {
                                    if (ob.name === 'loaded') {
                                        loaded++
                                    }
                                }
                            )

                            if (loaded === len) {
                                ws.current.send('1')
                            } else {
                                ws.current.send('0')
                            }
                        } catch (err) {
                            ws.current.send('0')
                        }
                    }
                    break

                case 'shape':
                    {
                        const id = shapeDesc.length.toString()
                        setShapeDesc([...shapeDesc, data])
                        ws.current.send(id)
                    }
                    break

                case 'shape_poses':
                    data.forEach((object) => {
                        const id = object[0]
                        const group = object[1]

                        group.forEach((pose, i) => {
                            shapes.current.children[id].children[
                                i
                            ].position.set(pose.t[0], pose.t[1], pose.t[2])

                            let quat = new THREE.Quaternion(
                                pose.q[0],
                                pose.q[1],
                                pose.q[2],
                                pose.q[3]
                            )

                            shapes.current.children[id].children[
                                i
                            ].setRotationFromQuaternion(quat)

                            // console.log(
                            //     shapes.current.children[id].children[i]
                            //         .quaternion
                            // )
                            // console.log(shapes.current.children[id].children[i])
                            // // mesh.setRotationFromQuaternion(quat);
                            // shapes.current.children[id].children[
                            //     i
                            // ].setRotationFromQuaternion(quat)
                            // shapes.current.children[id].children[
                            //     i
                            // ].quaternion.set(
                            //     pose.q[0],
                            //     pose.q[1],
                            //     pose.q[2],
                            //     pose.q[3]
                            // )
                            // console.log(shapes.current.children[id].children[i])
                            // console.log(pose.q)
                            // console.log(0)
                        })
                    })
                    ws.current.send('0')
                    break
                default:
                    break
                // ws.send(id);
            }
        }
    }, [shapeDesc])

    return (
        <div className={styles.swiftContainer}>
            <Canvas gl={{ antialias: true }} shadowMap={{ enabled: true }}>
                <Camera setDefault={true} />
                {hasMounted && (
                    <Suspense fallback={null}>
                        <Controls />
                    </Suspense>
                )}
                <hemisphereLight skyColor={0x443333} groundColor={0x111122} />
                <ShadowedLight
                    x={10}
                    y={10}
                    z={10}
                    color={0xffffff}
                    intensity={0.2}
                />
                <ShadowedLight
                    x={-10}
                    y={-10}
                    z={10}
                    color={0xffffff}
                    intensity={0.2}
                />

                <Plane />
                <axesHelper args={[100]} />

                <GroupCollection meshes={shapeDesc} ref={shapes} />
                {/* <Shape
                    stype={'mesh'}
                    scale={[0.5, 0.5, 0.5]}
                    filename={'vercel.svg'}
                    t={[-0.5, 0, 0.5]}
                    opacity={0.3}
                />

                <Shape
                    stype={'mesh'}
                    scale={[0.5, 0.5, 0.5]}
                    filename={'one.stl'}
                    t={[0.0, 1.0, 0.5]}
                    opacity={0.3}
                />

                <Shape
                    stype={'mesh'}
                    scale={[10, 10, 10]}
                    filename={'BoomBox.glb'}
                    t={[0.0, 0.0, 0.5]}
                    opacity={0.5}
                />

                <Shape
                    stype={'mesh'}
                    scale={[0.001, 0.001, 0.001]}
                    filename={'2cylinderengine.gltf'}
                    t={[0.5, 0.0, 0.5]}
                    opacity={0.9}
                /> */}

                {/* <Shape
                    stype={'mesh'}
                    scale={[1, 1, 1]}
                    filename={'walle.dae'}
                    t={[0.0, -1.5, 0.0]}
                    q={[0, 0, 0, 1]}
                    opacity={0.2}
                />

                <Shape
                    stype={'mesh'}
                    scale={[1, 1, 1]}
                    filename={'walle.dae'}
                    t={[0.0, 0.5, 0.0]}
                    q={[0, 0, 0, 1]}
                    opacity={0.2}
                /> */}

                {/* <Shape
                    stype={'mesh'}
                    scale={[1, 1, 1]}
                    filename={'walle.obj'}
                    t={[0.0, -2, 0.0]}
                    opacity={0.4}
                />

                <Shape
                    stype={'mesh'}
                    scale={[1, 1, 1]}
                    filename={'walle.wrl'}
                    t={[0.0, -3, 0.0]}
                    opacity={0.4}
                />

                <Shape
                    stype={'mesh'}
                    scale={[1, 1, 1]}
                    filename={'walle.ply'}
                    t={[1.5, 0, 0.0]}
                    opacity={0.8}
                />

                <Shape
                    stype={'mesh'}
                    scale={[0.004, 0.004, 0.004]}
                    filename={'sheep.fbx'}
                    t={[0, 0.4, 0.3]}
                    opacity={0.1}
                />

                <Shape
                    stype={'mesh'}
                    scale={[1, 1, 1]}
                    filename={'model.pcd'}
                    t={[1, 1, 0.5]}
                    opacity={0.5}
                    color={0x123456}
                /> */}
            </Canvas>
        </div>
    )
}

export default Swift
