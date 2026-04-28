import React from 'react';
import MainHeader from '../../components/MainHeader';
import MainTop from './MainTop';
import MainBody from './MainBody';

function Main() {
  return (
    <>
      <MainHeader />
      <div className="container mt-4">
        <MainTop />
        <MainBody />
      </div>
    </>
  );
}

export default Main;