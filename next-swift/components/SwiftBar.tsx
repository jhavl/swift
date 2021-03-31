import React, { useState, useEffect, useRef, lazy, Suspense } from 'react'
import styles from '../styles/SwiftBar.module.scss'

export interface ISwiftElement {
    element: string
    id: number
    callback?: any
    desc?: string
    min?: number
    max?: number
    value?: number[]
    step?: number
    unit?: string
    options?: string[]
    checked?: boolean[]
}

export interface ISwiftBar {
    elements: ISwiftElement[]
}

const SwiftButton = (props: ISwiftElement): JSX.Element => {
    const callback = (e) => {
        props.callback(props.id, 1)
    }

    return (
        <div className={styles.buttonDiv}>
            <button
                type="button"
                className={styles.buttonButton}
                id={'button' + props.id}
                onClick={callback}
            >
                {props.desc}
            </button>
        </div>
    )
}

const SwiftLabel = (props: ISwiftElement): JSX.Element => {
    return (
        <div className={styles.labelDiv}>
            <p id={'label' + props.id}>{props.desc}</p>
        </div>
    )
}

const SwiftSlider = (props: ISwiftElement): JSX.Element => {
    const slider = useRef(null)
    const label = useRef(null)

    const callback = (e) => {
        label.current.innerHTML = slider.current.value + props.unit
        props.callback(props.id, slider.current.value)
    }

    useEffect(() => {
        console.log(props.value)
        slider.current.value = props.value[0]
        label.current.innerHTML = props.value[0] + props.unit
    }, [props.value])

    return (
        <div className={styles.sliderDiv} id={'slider-div' + props.id}>
            <p className={styles.sliderP} id={'desc' + props.id}>
                {props.desc}
            </p>
            <input
                ref={slider}
                type="range"
                defaultValue={props.value[0]}
                step={props.step}
                min={props.min}
                max={props.max}
                className={styles.slider}
                id={'slider' + props.id}
                onInput={callback}
            />

            <div
                className={styles.sliderValDiv}
                id={'slider-val-div' + props.id}
            >
                <p
                    className={[styles.sliderVals, styles.sliderMin].join(' ')}
                    id={'min' + props.id}
                >
                    {props.min}
                </p>
                <p
                    ref={label}
                    className={[styles.sliderVals, styles.sliderVal].join(' ')}
                    id={'value' + props.id}
                >
                    {slider.current
                        ? slider.current.value + props.unit
                        : props.value[0] + props.unit}
                </p>
                <p
                    className={[styles.sliderVals, styles.sliderMax].join(' ')}
                    id={'max' + props.id}
                >
                    {props.max}
                </p>
            </div>
        </div>
    )
}

const SwiftSelect = (props: ISwiftElement): JSX.Element => {
    const select = useRef(null)

    const callback = (e) => {
        props.callback(props.id, select.current.value)
    }

    useEffect(() => {
        select.current.value = props.value[0]
    }, [props.value])

    return (
        <div className={styles.selectDiv}>
            <label id={'label' + props.id} className={styles.selectLabel}>
                {props.desc}
            </label>
            <select
                ref={select}
                id={'select' + props.id}
                className={styles.selectSelect}
                onChange={callback}
                defaultValue={props.value[0]}
            >
                {props.options.map((value, i) => {
                    return (
                        <option key={props.id + ' ' + i} value={i}>
                            {value}
                        </option>
                    )
                })}
            </select>
        </div>
    )
}

const SwiftCheckbox = (props: ISwiftElement): JSX.Element => {
    const check = useRef(null)

    const callback = (e) => {
        const checks = check.current.getElementsByTagName('input')
        const data = []
        for (let i = 0; i < checks.length; i++) {
            data.push(checks[i].checked)
        }
        props.callback(props.id, data)
    }

    useEffect(() => {
        const checks = check.current.getElementsByTagName('input')
        for (let i = 0; i < checks.length; i++) {
            checks[i].checked = props.checked[i]
        }
    }, [props.checked])

    return (
        <div className={styles.checkboxDiv}>
            <label className={styles.checkboxLabel} id={'label' + props.id}>
                {props.desc}
            </label>
            <div
                ref={check}
                onChange={callback}
                className={styles.checkboxCont}
                id={'checkboxcont' + props.id}
            >
                {props.options.map((value, i) => {
                    return (
                        <label
                            htmlFor={'checkbox' + props.id}
                            key={props.id + ' ' + i}
                        >
                            <input
                                type={'checkbox'}
                                defaultChecked={props.checked[i]}
                                id={'checkbox' + props.id + i}
                            />
                            <span> {props.options[i]} </span>
                        </label>
                    )
                })}
            </div>
        </div>
    )
}

const SwiftRadio = (props: ISwiftElement): JSX.Element => {
    const radio = useRef(null)

    useEffect(() => {
        const radios = radio.current.getElementsByTagName('input')
        for (let i = 0; i < radios.length; i++) {
            radios[i].checked = props.checked[i]
        }
    }, [props.checked])

    const callback = (e) => {
        const radios = radio.current.getElementsByTagName('input')
        let i
        for (i = 0; i < radios.length; i++) {
            if (radios[i].checked) {
                break
            }
        }
        props.callback(props.id, i)
    }

    return (
        <div className={styles.radioDiv}>
            <label className={styles.radioLabel} id={'label' + props.id}>
                {props.desc}
            </label>
            <div
                ref={radio}
                onChange={callback}
                className={styles.radioCont}
                id={'radiocont' + props.id}
            >
                {props.options.map((value, i) => {
                    return (
                        <label
                            htmlFor={'radio' + props.id}
                            key={props.id + ' ' + i}
                        >
                            <input
                                type={'radio'}
                                defaultChecked={props.checked[i]}
                                id={'radio' + props.id + i}
                                name={'radio' + props.id}
                            />
                            <span> {props.options[i]} </span>
                        </label>
                    )
                })}
            </div>
        </div>
    )
}

const SwiftElement = (props: ISwiftElement): JSX.Element => {
    switch (props.element) {
        case 'button':
            return <SwiftButton {...props} />
            break

        case 'label':
            return <SwiftLabel {...props} />
            break

        case 'slider':
            return <SwiftSlider {...props} />
            break

        case 'select':
            return <SwiftSelect {...props} />
            break

        case 'checkbox':
            return <SwiftCheckbox {...props} />
            break

        case 'radio':
            return <SwiftRadio {...props} />
            break

        default:
            return <SwiftButton {...props} />
            break
    }
}

const SwiftBar = (props: ISwiftBar): JSX.Element => {
    const [pauseB, setPauseB] = useState('icons/pause.svg')

    return (
        <div
            className={styles.sidenav}
            hidden={props.elements.length > 0 ? false : true}
        >
            {props.elements.map((value, i) => {
                return <SwiftElement key={'element ' + i} {...value} />
            })}
        </div>
    )
}

export default SwiftBar
