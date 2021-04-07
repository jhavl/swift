import React, { useEffect, useRef, useContext } from 'react'
import { FormDispatch } from '../components/Swift'
import styles from '../styles/SwiftBar.module.scss'

export interface ISwiftElement {
    element: string
    id: number
    desc?: string
    min?: number
    max?: number
    value?: number
    step?: number
    unit?: string
    options?: string[]
    checked?: boolean[]
}

export interface ISwiftBar {
    elements: ISwiftElement[]
}

function useTraceUpdate(props) {
    const prev = useRef(props)
    useEffect(() => {
        const changedProps = Object.entries(props).reduce((ps, [k, v]) => {
            if (prev.current[k] !== v) {
                ps[k] = [prev.current[k], v]
            }
            return ps
        }, {})
        if (Object.keys(changedProps).length > 0) {
            console.log('Changed props:', changedProps)
        }
        prev.current = props
    })
}

const SwiftButton = (props: ISwiftElement): JSX.Element => {
    const dispatch = useContext(FormDispatch)

    return (
        <div className={styles.buttonDiv}>
            <button
                type="button"
                className={styles.buttonButton}
                id={'button' + props.id}
                onClick={() =>
                    dispatch({
                        type: 'userInputNoState',
                        index: props.id,
                        data: 1,
                    })
                }
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
    const dispatch = useContext(FormDispatch)
    const slider = useRef(null)
    const label = useRef(null)

    const updateSlider = () => {
        label.current.innerHTML = slider.current.value + props.unit
        dispatch({
            type: 'userInputState',
            index: props.id,
            data: parseFloat(slider.current.value),
            valueName: 'value',
            value: parseFloat(slider.current.value),
        })
    }

    useEffect(() => {
        updateSlider()
    }, [props.value])

    // useTraceUpdate(props)

    return (
        <div className={styles.sliderDiv} id={'slider-div' + props.id}>
            <p className={styles.sliderP} id={'desc' + props.id}>
                {props.desc}
            </p>
            <input
                ref={slider}
                type="range"
                value={props.value}
                step={props.step}
                min={props.min}
                max={props.max}
                className={styles.slider}
                id={'slider' + props.id}
                onInput={updateSlider}
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
                    {props.value + props.unit}
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
    const dispatch = useContext(FormDispatch)
    const select = useRef(null)

    const updateSelect = (e) => {
        dispatch({
            type: 'userInputState',
            index: props.id,
            data: parseInt(select.current.value),
            valueName: 'value',
            value: parseInt(select.current.value),
        })
    }

    useEffect(() => {
        dispatch({
            type: 'userInputNoState',
            index: props.id,
            data: parseInt(select.current.value),
        })
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
                onChange={updateSelect}
                value={props.value}
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
    const dispatch = useContext(FormDispatch)
    const check = useRef(null)

    const getChecked = () => {
        const checks = check.current.getElementsByTagName('input')
        const data = []
        for (let i = 0; i < checks.length; i++) {
            data.push(checks[i].checked)
        }
        return data
    }

    const updateCheckbox = (e) => {
        const checked = getChecked()

        dispatch({
            type: 'userInputState',
            index: props.id,
            data: checked,
            valueName: 'checked',
            value: checked,
        })
    }

    useEffect(() => {
        const checked = getChecked()

        dispatch({
            type: 'userInputNoState',
            index: props.id,
            data: checked,
        })
    }, [props.checked])

    return (
        <div className={styles.checkboxDiv}>
            <label className={styles.checkboxLabel} id={'label' + props.id}>
                {props.desc}
            </label>
            <div
                ref={check}
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
                                onChange={updateCheckbox}
                                checked={props.checked[i]}
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
    const dispatch = useContext(FormDispatch)
    const radio = useRef(null)

    const getChecked = () => {
        const radios = radio.current.getElementsByTagName('input')
        let i, j
        let checked = []
        for (i = 0; i < radios.length; i++) {
            if (radios[i].checked) {
                j = i
            }
            checked.push(radios[i].checked)
        }
        return [checked, j]
    }

    const updateRadio = () => {
        const [checked, j] = getChecked()

        dispatch({
            type: 'userInputState',
            index: props.id,
            data: j,
            valueName: 'checked',
            value: checked,
        })
    }

    useEffect(() => {
        const [checked, j] = getChecked()

        dispatch({
            type: 'userInputNoState',
            index: props.id,
            data: j,
        })
    }, [props.checked])

    return (
        <div className={styles.radioDiv}>
            <label className={styles.radioLabel} id={'label' + props.id}>
                {props.desc}
            </label>
            <div
                ref={radio}
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
                                onChange={updateRadio}
                                checked={props.checked[i]}
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
    if (props.element === 'button') return <SwiftButton {...props} />
    if (props.element === 'label') return <SwiftLabel {...props} />
    if (props.element === 'slider') return <SwiftSlider {...props} />
    if (props.element === 'select') return <SwiftSelect {...props} />
    if (props.element === 'checkbox') return <SwiftCheckbox {...props} />
    if (props.element === 'radio') return <SwiftRadio {...props} />
    return <SwiftButton {...props} />
}

const SwiftBar = (props: ISwiftBar): JSX.Element => {
    return (
        <div
            className={styles.sidenav}
            hidden={props.elements.length > 0 ? false : true}
        >
            {props.elements.map((value, i) => {
                return <SwiftElement key={value.id.toString() + i} {...value} />
            })}
        </div>
    )
}

export default SwiftBar
