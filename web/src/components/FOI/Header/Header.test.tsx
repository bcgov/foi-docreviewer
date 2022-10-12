import Header from "./Header";
import configureStore from 'redux-mock-store';
import renderer from 'react-test-renderer';
import { Provider } from 'react-redux';
import {expect, jest} from '@jest/globals';
import * as ShallowRenderer from 'react-test-renderer/shallow';

const mockedHeader = jest.fn<any>();
const shallowRenderer = ShallowRenderer.createRenderer();

describe('Header component', () => {

    beforeEach(() => {
        mockedHeader.mockImplementation((callback: () => any) => {
            return callback();
        });
    });
    afterEach(() => {
        mockedHeader.mockClear();
    });

    const initialState = { output: 10 }
    const mockStore = configureStore()
    let store

    it("Header Rendering Unit test - shallow check", () => {
        store = mockStore(initialState)
        const localState = {
            isAuthenticated: true,
            user: {
                name: 'John',
                preferred_username: 'John Smith'
            }
        }
        mockedHeader.mockImplementation((callback: (arg0: { isAuthenticated: boolean; user: { name: string; preferred_username: string; }; }) => any) => {
            return callback(localState);
        });
        shallowRenderer.render(<Provider store={ store } > <Header /> </Provider >)
    });

    it('FOI header snapshot check', () => {
        store = mockStore(initialState)
        const localState = {
            isAuthenticated: true,
            user: {
                name: 'John',
                preferred_username: 'John Smith'
            }
        }
        mockedHeader.mockImplementation((callback: (arg0: { isAuthenticated: boolean; user: { name: string; preferred_username: string; }; }) => any) => {
            return callback(localState);
        });
        const tree = renderer.create(<Provider store={ store } > <Header /></Provider >).toJSON();
        expect(tree).toMatchSnapshot();
    })
})