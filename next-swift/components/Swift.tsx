import * as THREE from 'three'
THREE.Object3D.DefaultUp.set(0, 0, 1)
import React, {
    useState,
    useEffect,
    useCallback,
    useReducer,
    useRef,
    lazy,
    Suspense,
} from 'react'
import { Canvas, useFrame } from 'react-three-fiber'
import SwiftInfo from '../components/SwiftInfo'
import SwiftBar, { ISwiftBar, ISwiftElement } from '../components/SwiftBar'
import styles from '../styles/Swift.module.scss'
import formReducer, { DEFUALT_ELEMENTS } from './Swift.reducer'

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

const GroupCollection = React.forwardRef<THREE.Group, IGroupCollection>(
    (props, ref): JSX.Element => {
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
export const FormDispatch = React.createContext(null)

const Swift: React.FC<ISwiftProps> = (props: ISwiftProps): JSX.Element => {
    const [hasMounted, setHasMounted] = useState(false)
    const [time, setTime] = useState(0.0)
    const [FPS, setFPS] = useState('60 fps')
    const [frameTime, setFrameTime] = useState([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    const [frameI, setFrameI] = useState(0)
    const shapes = useRef<THREE.Group>()
    const ws = useRef<WebSocket>(null)
    const [shapeDesc, setShapeDesc] = useState<IShapeProps[][]>([])
    const [connected, setConnected] = useState(false)
    const [formState, formDispatch] = useReducer(formReducer, {
        formData: {},
        formElements: [],
    })

    const setFrames = useCallback((delta) => {
        let newFrameTime = [...frameTime]
        let newFrameI = frameI
        let total = 0

        newFrameI += 1
        if (newFrameI >= 10) {
            newFrameI = 0
        }

        newFrameTime[newFrameI] = delta

        for (let j = 0; j < 10; j++) {
            total += newFrameTime[j]
        }

        total = Math.round(total / 10.0)

        // setFrameTime(newFrameTime)
        // setFrameI(newFrameI)
        // if (total === Infinity) {
        //     total = 60
        // }
        // setFPS(`${total} fps`)
    }, [])

    useEffect(() => {
        setHasMounted(true)
        let port = props.port

        if (port === 0) {
            port = parseInt(window.location.search.substring(1))
        }

        if (!port) {
            port = 0
        }

        ws.current = new WebSocket('ws://localhost:' + port + '/')
        ws.current.onopen = () => {
            ws.current.onclose = () => {
                setTimeout(function () {
                    window.close()
                }, 5000)
            }

            ws.current.send('Connected')
            setConnected(true)
        }
    }, [])

    useEffect(() => {
        ;(ws.current.onmessage = (event) => {
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

                case 'remove':
                    const newShapeDesc = [...shapeDesc]
                    newShapeDesc[data] = []
                    setShapeDesc(newShapeDesc)
                    ws.current.send('0')
                    break

                case 'shape_poses':
                    if (Object.keys(formState.formData).length !== 0) {
                        ws.current.send(JSON.stringify(formState.formData))

                        formDispatch({
                            type: 'reset',
                            indices: Object.keys(formState.formData),
                        })
                    } else {
                        ws.current.send('[]')
                    }

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
                        })
                    })
                    break

                case 'sim_time':
                    setTime(parseFloat(data))
                    break

                case 'close':
                    ws.current.close()
                    window.close()
                    break

                case 'element':
                    formDispatch({ type: 'newElement', data: data })
                    ws.current.send('0')

                    break

                case 'update_element':
                    formDispatch({
                        type: 'wsUpdate',
                        index: data.id,
                        data: data,
                    })
                    break

                default:
                    break
            }
        }),
            [shapeDesc, formState]
    })

    return (
        <div className={styles.swiftContainer}>
            <FormDispatch.Provider value={formDispatch}>
                <SwiftInfo time={time} FPS={FPS} connected={connected} />
                <SwiftBar elements={formState.formElements} />
            </FormDispatch.Provider>

            <Canvas gl={{ antialias: true }} shadowMap={{ enabled: true }}>
                <Camera setDefault={true} fpsCallBack={setFrames} />
                {hasMounted && (
                    <Suspense fallback={null}>
                        <Controls />
                    </Suspense>
                )}
                <hemisphereLight
                    skyColor={new THREE.Color(0x443333)}
                    groundColor={new THREE.Color(0x111122)}
                />
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
