import React, { useState, useEffect, useRef, lazy, Suspense } from 'react'
import styles from '../styles/SwiftInfo.module.scss'

export interface ISwiftInfo {
    time: number
    FPS: string
    callback: any
    connected: boolean
}

export interface ISwiftAction {
    path: string
    onClick: any
    title: string
    connected: boolean
}

const convertTime = (time: number): string => {
    let s = Math.floor(time)
    let m = Math.floor(s / 60)
    let ms = (time * 1000) % 1000

    let sS = ''
    let mS = ''
    let msS = ''

    ms = Math.round(ms)

    s = s % 60

    if (s < 10) {
        sS = '0' + s
    } else {
        sS = s.toString()
    }

    if (m < 10) {
        mS = '0' + m
    } else {
        mS = m.toString()
    }

    if (ms < 10) {
        ms *= 100
    } else if (ms < 100) {
        ms *= 10
    }

    if (ms === 0) {
        msS = '000'
    } else {
        msS = ms.toString()
    }

    return `${mS}:${sS}.${msS}`
}

const SwiftAction = (props: ISwiftAction): JSX.Element => {
    return (
        <button
            className={styles.button}
            onClick={props.onClick}
            title={props.title}
            disabled={props.connected}
        >
            <img className={styles.svg} src={props.path} />
            {/* <span className={styles.sr}>Clink me</span> */}
        </button>
    )
}

const SwiftInfo = (props: ISwiftInfo): JSX.Element => {
    const [pauseB, setPauseB] = useState('icons/pause.svg')
    const [timeB, setTimeB] = useState('icons/realtime.svg')
    const [renderB, setRenderB] = useState('icons/stopRender.svg')
    const [pauseT, setPauseT] = useState('Pause the simulation')
    const [timeT, setTimeT] = useState('Play at real-time')
    const [renderT, setRenderT] = useState(
        'Stop rendering (simulation continues)'
    )
    const [paused, setPaused] = useState(false)
    const [fasttime, setFastTime] = useState(true)
    const [rendering, setRendering] = useState(true)
    const PAUSE_ID = 0
    const TIME_ID = 1
    const RENDER_ID = 2

    const pause = () => {
        let newPaused
        if (paused) {
            setPauseT('Pause the simulation')
            setPauseB('icons/pause.svg')
            newPaused = false
        } else {
            setPauseT('Continue the simulation')
            setPauseB('icons/play.svg')
            newPaused = true
        }
        setPaused(newPaused)
        props.callback(PAUSE_ID, newPaused)
    }

    const realtime = () => {
        let newFasttime
        if (fasttime) {
            setTimeT('Play at full speed')
            setTimeB('icons/fasttime.svg')
            newFasttime = false
        } else {
            setTimeT('Play at real-time')
            setTimeB('icons/realtime.svg')
            newFasttime = true
        }
        setFastTime(newFasttime)
        props.callback(TIME_ID, newFasttime)
    }

    const startrender = () => {
        let newRendering
        if (rendering) {
            setRenderT('Start rendering')
            setRenderB('icons/startRender.svg')
            newRendering = false
        } else {
            setRenderT('Stop rendering (simulation continues)')
            setRenderB('icons/stopRender.svg')
            newRendering = true
        }
        setRendering(newRendering)
        props.callback(RENDER_ID, newRendering)
    }

    return (
        <div className={styles.info}>
            <div className={styles.spacer}></div>
            <SwiftAction
                path={pauseB}
                onClick={pause}
                title={pauseT}
                connected={!props.connected}
            />
            <SwiftAction
                path={timeB}
                onClick={realtime}
                title={timeT}
                connected={!props.connected}
            />
            <SwiftAction
                path={renderB}
                onClick={startrender}
                title={renderT}
                connected={!props.connected}
            />
            <div className={styles.fps}>{props.FPS}</div>
            <div className={styles.simTime}>{convertTime(props.time)}</div>
        </div>
    )
}

export default SwiftInfo
