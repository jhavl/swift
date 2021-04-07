export const DEFUALT_ELEMENTS = 3;

const formReducer = (state, action) => {
    console.log('action: ', action, "state ", state);
    switch (action.type) {
        case 'newElement':
            return {
                ...state,
                formElements: [...state.formElements, action.data],
            }

        case 'userInputState':
            const formData = { ...state.formData }
            const formElements = [...state.formElements]

            formData[action.index] = action.data
            // console.log(formData)

            formElements[action.index - DEFUALT_ELEMENTS][
                action.valueName
            ] = action.value;

            return {
                formElements: formElements,
                formData: formData,
            }

        case 'userInputNoState':
            const uiFormData = { ...state.formData }

            uiFormData[action.index] = action.data

            return {
                formElements: [...state.formElements],
                formData: uiFormData,
            }

        case 'wsUpdate':
            const updateFormElements = [...state.formElements];
            updateFormElements[action.index - DEFUALT_ELEMENTS] = action.data
            return {
                ...state,
                formElements: updateFormElements,
            }

        case 'reset':
            const newFormData = { ...state.formData }

            action.indices.map((val) => {
                delete newFormData[val]
            })

            return {
                formData: newFormData,
                formElements: [...state.formElements],
            }

        default:
            throw new Error()
    }
}

export default formReducer;