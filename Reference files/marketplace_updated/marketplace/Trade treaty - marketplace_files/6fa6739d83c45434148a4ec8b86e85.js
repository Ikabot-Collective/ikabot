function swapPositionsIfPossible(from, to) {
    if (typeof from !== "number" || typeof to !== "number") {
        return false;
    }
    const positionA = ikariam.backgroundView.screen.data.position[from];
    const positionB = ikariam.backgroundView.screen.data.position[to];

    if (positionA['buildingId'] === null) { // we always want at least a building in position A
        return false;
    }
    const positionBHasBuilding = positionB['buildingId'] !== null;

    // droppedPosition can accommodate dragged building
    if (!positionB['allowedBuildings'].includes(positionA['buildingId'])
        || positionBHasBuilding && !positionA['allowedBuildings'].includes(positionB['buildingId'])) {
        return false;
    }

    if (positionA['isBusy'] || positionB['isBusy']) {
        return false;
    }

    if (positionA['completed'] || positionB['completed']) { // currently being built
        return false;
    }

    if (positionA['inConstructionList'] || positionB['inConstructionList']) { // planned to get built
        return false;
    }

    if ($('#locations').find('.position' + to).hasClass('lockedPosition')) {
        return false;
    }

    const b = ikariam.backgroundView.screen.data.position[from];
    ikariam.backgroundView.screen.data.position[from] = ikariam.backgroundView.screen.data.position[to];
    ikariam.backgroundView.screen.data.position[to] = b;

    logSuccessfulMoves(from, to, positionBHasBuilding);
    ikariam.backgroundView.screen.update(ikariam.backgroundView.screen.data);
    return true;
}

function logSuccessfulMoves(from, to, positionBHasBuilding) {
    var previousMoveAFound = false;
    var previousMoveBFound = false;
    for (var i=0; i < ikariam.backgroundView.screen.positionMoveLog.length; ++i) {
        if (ikariam.backgroundView.screen.positionMoveLog[i].to === from) {
            previousMoveAFound = true;
            ikariam.backgroundView.screen.positionMoveLog[i].to = to;
            continue;
        }
        if (positionBHasBuilding && ikariam.backgroundView.screen.positionMoveLog[i].to === to) {
            previousMoveBFound = true;
            ikariam.backgroundView.screen.positionMoveLog[i].to = from;
        }
    }
    if (!previousMoveAFound) {
        ikariam.backgroundView.screen.positionMoveLog.push({ from, to });
    }
    if (positionBHasBuilding && !previousMoveBFound) {
        ikariam.backgroundView.screen.positionMoveLog.push({ from: to, to: from });
    }
    // console.dir(ikariam.backgroundView.screen.positionMoveLog)
}

function setDraggables() {
    $(".draggableElement").draggable({
        revert: true,
        start: function () {
            $('body').css('cursor', 'grabbing');
            $('.draggableElement').css('cursor', 'grabbing');
            $('#container #worldmap .buildingItem a.hoverable').css('cursor', 'grabbing');
        },
        stop: function () {
            $('body').css('cursor', 'default');
            $('.draggableElement').css('cursor', 'grab');
            $('#container #worldmap .buildingItem a.hoverable').css('cursor', 'grab');
        },
        helper: function () {
            return $(this)
                .parents('.buildingItem')
                .clone()
                .css('transform', 'scale(0.4)');

        }
    });
}

function setDroppables() {
    $(".draggableElement").droppable({
        accept: ".draggableElement",
        tolerance: "pointer",
        classes: {
            'ui-droppable-hover': 'ui-state-hover'
        },
        drop: function(event, ui) {
            const draggedBuildingItem = $(ui.draggable).parents('.buildingItem');
            const droppedOnBuildingItem = $(this).parents('.buildingItem');

            const draggedId = draggedBuildingItem.parent().data('id');
            const droppedId = droppedOnBuildingItem.parent().data('id');

            if(swapPositionsIfPossible(draggedId, droppedId)) {
                setDraggables();
                setDroppables();
            }
            draggedBuildingItem.css('top', "-44px").css('left',"-24px");
        }
    });
}

function setCityBuildingsDraggable() {
    if (touchVersion) {
        ikariam.controller.actionMonitor.abortBubble([ LocalizationStrings['TXT_MOBILE_FEATURE_NOT_AVAILABLE2'] ]);
        return;
    }
    window.reArrangeAjaxHandlerCall = window.ajaxHandlerCall;
    window.ajaxHandlerCall = function(aUrl) { console.log(aUrl + " ignored"); }
    window.ajaxHandlerCallFromForm = function(form) { console.log("form ignored"); }

    // we are switching off some JS below. the requests here can't be asynchronous, or they will wipe our changes again:
    reArrangeAjaxHandlerCall('?view=updateGlobalData', null, [], false); // has to be before the real view. otherwise #emailValidationReminderButton may show up again
    reArrangeAjaxHandlerCall('?view=saveCityBuildingsPositions', null, [], false);
    ikariam.getBackgroundView().stopPeriodicDataRefresh();

    $('#scrollcover')
        .off('scrollLeft')
        .off('scrollRight')
        .off('touchstart')
        .off('mousemove.dragMap')
        .off('scroll')
        .off('touchmove')
        .off('gesturestart')
        .off('gesturechange')
        .off('gestureend')
        .off('mousedown')
        .off('mouseup');
    var oldShow = ikariam.show;
    ikariam.show = function(type, popupId) { if (type === 'avatarNotes') { oldShow(type, popupId); }};

    ikariam.backgroundView.id = 'city';
    ikariam.backgroundView.screen.positionMoveLog = [];
    ikariam.backgroundView.screen.positionMoveCityId = ikariam.backgroundView.screen.screenId;

    $('a[id^="js_CityPosition"]').attr('onclick', 'return false;');
    $("#locations")
        .on('mouseenter', ' .draggableElement', function(){
            $(this).parent().find('.img_pos.hover').removeClass('invisible');
        })
        .on('mouseleave', ' .draggableElement', function(){
            $(this).parent().find('.img_pos.hover').addClass('invisible');
        });

    $('#city').addClass('draggable-city');
    $('#cityCinema, #cityCinema .animationLight, #cityCinema #cityCinemaLink, #city #cityAmbrosiaFountainLink,'
        + ' #city #cityDailyTasks, #cityFlyingShop, #cityFlyingShop .extras, #city #cityRegistrationGifts, #city #locations .building a')
        .on('dragstart', function (event) { event.preventDefault(); });

    $('#GF_toolbar .forum a').attr('href', null);
    $('#resizablepanel_chat').hide();
    $('#js_viewFriends .pageup, #js_viewFriends .pagedown').off('click');

    setDraggables();
    setDroppables();
    $('#js_citySelectContainer .dropDownButton').off('click');
    $('body').on('keyup', function (e) {
        if (e.key === 'Escape' || e.key === 'Esc') {
            window.location.reload();
        }
    });

    if (!ikariam.getMapNavigation().expanded) {
        ikariam.getMapNavigation().toggleControls();
    }
}

function clickSaveBuildingPositionsExecuteButton() {
    reArrangeAjaxHandlerCall(
        '?action=SaveBuildingPositions',
        null,
        {
            moves: ikariam.backgroundView.screen.positionMoveLog,
            cityId:  ikariam.backgroundView.screen.positionMoveCityId
        }
    );
    ikariam.backgroundView.screen.positionMoveLog = [];
    ikariam.backgroundView.screen.positionMoveCityId = null;
    return false;
}