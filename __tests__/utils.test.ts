import * as Utils from '../src/utils';
describe('Git Abstraction Utils', () => {
  test('isSubsequence matches discontinuous fuzzy queries', () => {
    expect(Utils.isSubsequence('cafe', 'cat fanciers')).toBe(true);
  });
});
