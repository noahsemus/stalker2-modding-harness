# Game console commands

The retail game's console commands (mostly `X*`) with their argument names, as collected in 2026-10 for game patch
2.0.x. **Grep this page before guessing a command name or digging through the exe.** Spellings are the game's
own, typos included (`XShowInventoryDebugItmesStats`, `XShowPopupSaveSettinsRestart`, `XChangeCompasMarkers`).

## Facts and traps
- Commands also run from quest data: a quest node `NodeType = EQuestNodeType::ConsoleCommand` with
  `ConsoleCommand = <command line>` (vanilla uses it, e.g. `XStartQuestNodeBySID <SID>`,
  `XDeactivateAIFeature ALifeDirector`, `XSwitchPlayerRank Master`, even `setbind x xkillnpcinradius ...`; kit
  `QuestNodePrototypes/*.cfg`). A mod can drive repeated work through a few such nodes and avoid quest-node fan-out
  (`saves.md` § name limit).
- **`XPrintGlobalVariable SID` prints nothing** (2026-10-24), neither in the in-game console nor through an external
  command injector. Do not use it to read quest/global variables; check the effect in game (a spawn, a branch, a
  debug fade-screen node).
- **Ending quests under a running game can crash it.** `XEndQuestBySID <quest>` sent for several quests whose
  `ConsoleCommand` nodes were mid-flight crashed the game (2026-10-29: null write under the console exec path).
  Treat `XEnd*` / `XReset*` / `XExclude*` / `XSkipToQuestNode` as destructive: describe the command and its risk and
  let the tester decide; prefer them on a throwaway save.
- `Stalker2.log` holds no lines about the game itself or mods: no console commands, effects, quest nodes or mod
  subsystems (`diagnostics.md`). Verify a command by its in-game effect.
- Arguments: `SID` = prototype/quest SID from the cfgs; `UID` = runtime object id (`XShowUnitAndSquadUIDs Radius`,
  `XGetActorNameByUID`); `ID` variants take numeric ids. Booleans are written `true|false` in some entries.
- Examples in the list: `XSpawnObjBySID GeneralNPC_Duty_Stormtrooper 2 0 0 0 0 0 0 0`,
  `XCreateItemInInventoryByID Milk 0 1 1`, `XSetGodMode true`.

## Quests and quest nodes
```
XStartQuestBySID SID            XStartQuest ID              XDKStartQuest SID
XStartQuestNodeBySID SID        XStartQuestNode ID          XDKStartQuestStage QSID SSID
XEndQuestBySID SID              XEndQuest ID                XDKStartTwoQuestStage QSID
XEndQuestNodeBySID SID          XEndQuestNode ID            XDKFinishQuest SID bWin
XExcludeQuestBySID SID          XExcludeQuest ID            XDKFinishQuestStage QSID SSID bWin
XExcludeQuestNodeBySID SID      XExcludeQuestNode ID        XSkipToQuestNode SID
XResetQuestBySID SID            XResetRandomNodeBySID SID   XResetRandomNode ID
XSetRandomNodeDefinedPinBySID SID PinNumber                 XSetRandomNodeDefinedPin ID PinNumber
XPrintGlobalVariable SID (broken)   XSetGlobalSID InValue   XSetGlobalObjectPath SID InValue
XShowQuestTriggers true|false   XShowCurrentImportantChoices   XExecuteAdditionalScript ScriptKeyName
XTestJournal  XTestJournalFinishQuest  XTestJournalQuestRewardCategory QuestSID
```

## Spawning, killing, NPCs and A-Life
```
XSpawnObjBySID PrototypeSID Rank bDestroyOnOffline Px Py Pz Pitch Yaw Roll
XSpawnPsyNPC bIsPsyPhantom ObjPrototypeSID Rank Count       XSpawnDeadNpc
XSpawnALifeDirectorScenario ScenarioSID                     XSpawnItemContainer PrototypeID Px Py Pz Gold Pitch Yaw Roll
XKillNpcByUID NpcUID   XKillThemAll   XKillNPCInRadius Radius MinimalReputationToKill MaxReputationToKill
XWoundNpcByUID NpcUID  XKnockDownNpc NpcUID  XKnockDownNpcByAnotherNpc NpcUID AttackerNpcUID
XResurrectNPCAsZombie NpcUID   XDespawnNPCsAtRadius Radius   XDespawnAliveNPCsAtRadius Radius   XDespawnDeadNPCsAtRadius Radius
XTeleportNPCToPlayer NPCSID    XTeleportNPCToSpawn NPCSID    XMoveToPlayer NPC_UID Behaviour   XAddMoveTo UID
XResetAI UID   XSetAIStayGoal ObjUID AnimPath   XNPCAddAbility NpcUID AbilityTag   XNPCRemoveAbility NpcUID AbilityTag
XNpcSetStateTag NpcUID StateTag bEnabled   XNpcLookAt NpcUID X Y Z   XNpcLookAtNPC NpcUID TargetNpcUID
XNpcSetLookAtOwnerState NpcUID LookAtOwnerState   XLimitNpcBodyPartRotation NpcUID LimitAngle RotationPartType
XNpcFreezeRagdollPose NpcUID   XSimulatePhysicsOnBoneForObj ObjUID BoneName   XToggleNPCFlashlight UID
XNpcSetFaceBlendShapeState NpcUID bEnabled   XNpcArraySetFaceBlendShapeState StartNpcUID bEnabled
XNpcSetFaceBlockingBlendMask NpcUID FaceBlockingMask BlockingWeight
XLaunchCustomAnimation ObjUID AnimPath AnimSlotName   XLaunchFacialAnimation ObjUID AnimPath
XALifeEnable  XALifeDisable  XALifeKillAll   XActivateAIFeature Feature   XDeactivateAIFeature Feature
XProtectSquad SquadUID bProtect   XShowUnitAndSquadUIDs Radius   XGetActorNameByUID UID   TransformUID UID
GetRelationBetween LHS RHS   XSetRelationsInRadius Radius RelationValue   XSVFriendlyFire bEnabled
XSetEntityUnkillableByUID bGodModeState   XSetGodModeByUID bGodModeState   XSetFactionGodMode CurrentFactionSelector bGodModeState
XSetGodModeAllFactions bGodModeState   XSetGodModeForInteractObj bGodMode   XPossessToCharacterByUID UID
XSetPsyNPCFilterParams bIsPsyPhantom AgentType1 AgentType2 ObjPrototypeFilter1 ObjPrototypeFilter2 ObjPrototypeFilter3
XSetClosestFaustCloneSwitchValue SearchRadius SwitchValue   StartFollowing TargetUID bLockOrientation double ZOffset   StopFollowing
```

## Player, damage, effects
```
XSetGodMode bGodMode   XSetNoClipGSC bNoClipGSC Speed   XSetPlayerSpeedMultiplier SpeedMultiplier   XSwitchPlayerRank Rank
XApplyEffectOnPlayer EffectPrototypeSID   XRemoveEffectFromPlayer EffectPrototypeSID
XApplyEffectOnNPCByUID EffectPrototypeSID UID   XApplyEffectOnInteractNPC EffectPrototypeSID
XDealDamage TargetUID Damage ArmorDamage ArmorPiercing Bleeding BleedingChanceIncrement Type BoneHit
XModifyBleeding TargetUID AddBleeding   XModifyStamina TargetUID FPSpent   XCommitSuicide DamageType   XSuicide
XObjRecalcAllCachedStats ObjUID   XObjRecalcAllEquipment ObjUID   XChangePlayerMovementFXPrototype PrototypeSID
XSetDifficultySID DifficultySID   XSetAimAssistEnabled bEnabled   XChangeDropBodyMethod bShouldDrop
XDisableLegsIK  XEnableLegsIK   XStartSleep
```

## Items, inventory, weapons, money
```
XSpawnItemNearPlayerBySID ItemPrototypeSID   XSpawnItemInCoordinatesBySID ItemPrototypeSID Px Py Pz
XCreateItemInInventoryByID PrototypeID ObjUID Count Durability   XGiveWeaponWithAttaches   XAddMoneyToPlayer Value
XApplyUpgradeBySID ItemPrototypeSID UpgradePrototypeSID   XRevertUpgradeBySID ItemPrototypeSID UpgradePrototypeSID
XApplyMainHandWeaponUpgradeBySID UpgradePrototypeSID   XRepairCurrentWeapon   XDisassemblyCurrentWeapon
XDealDurabilityDamage ItemUID DurabilityDamage   XResetCurrentWeaponDurabilityToZero   XResetCurrentBodyArmorDurabilityToZero
XPrintInventory UnitUID   XRegenerateItemsInStashes   XProtectItemContainer ContainerUID bProtect   XShowDebugInfoForStash InStashIdentifier
XReloadAttach  XReloadAttachTactical  XShootAttach   XWeaponDrag ModelUID Delay
XBlockItemSelectorSlot InBlock InSlotNum   XBlockItemSelectorSlots InBlock   XAddItemDragToQuickSlot IndexSlot
MoveItemsInTrade bMoveTraderItems bMoveOwnItems bMoveBarterItems   XTestSetDiscount InbDiscount   XToggleDrawCurrentDiscounts
UseStackSplitContextual bInUse   AllwaysShowDropHere bShow   XChangeInventoryScroll Index   XDrawDebugInventoryNavigation bDraw
XSetInventoryGamepadInputDelay InputDelay   XSetInventoryGamepadInputSelectionDelay InputSelectionDelay
XSetInventoryGamepadInputThreshold InputThreshold   XSetInventoryGamepadNavigationByAxises bAxes
XSetInventoryGamepadNavigationParams InputDelay InputThreshold SelectionDelay   XShowInventoryDebugItmesStats bShow
```

## World: teleport, time, weather, emission, anomalies, doors
```
XTeleportTo XCoord YCoord ZCoord   XTeleportToObjUID ObjUID   XTeleportToPlacesOfInterest SID
XTeleportPlayerInForwardDirection Distance Delay   XTeleportPlayerWithFade Distance   XVideoTeleportPlayerWithFade Distance
XShowPlayerCoordinates   XShowCurrentLocation   XEnterRegion RegionSID   GoToMap MapName   XEnsureAllRelevantCollisionStreamed
XSetGameTime Hour Minute Second   XSkipTimeHours uHours   XSetTimeSpeed Speed   XSetTwelveHourTime bSet
XForceWeather WeatherType   XSwitchToWeather WeatherType   XSetWeatherLocked bNowLocked
XSetWeatherTime Hour Minute Second   XSetWeatherTransitionTimeMultiplier WeatherTransitionTimeMultiplier
XStartEmission   XStartEmissionBySID PrototypeSID   XStopEmission   XGetEmissionState
XPauseScheduledEmission   XResumeScheduledEmission
XSetArtifactSpawnLuck LuckValue   XDisplayArtifactSpawnLuckStatus ArtifactSpawnerSID   XToggleArtifactSpawnerDebugInfo
XSwitchAnomalySpawnerPreset   XSetCarouselAngle Angle   XSetCarouselDuration Duration   XSetCarouselForce Force   XSetCarouselLiftUpTime Time
XSetCarouselRotation Rotation   XSetCarouselTimeToCenter Time   XSetCarouselDebugTrajectory bEnable
XOpenDoor DoorUID   XUnlockDoor DoorUID   XToggleHubDoors bLocked Radius   XShowHubOwner HubSID   XForceActorInteract ActorUID InteractableUID
XDiscoverMarker MarkerSID   XListMapMarkers MarkerType   XTryReceiveSignal Guid   XSignalStrengthTest
```

## Dialogs, notes, PDA, UI, language
```
XPlayDialogLine SpeakerUID DialogPrototypeSID   XPlayDialogFromPool DialogEventTypeName NPCUIDValue1 NPCUIDValue2
XPlayCommentFromPool DialogEventTypeName NPCUIDValue   XRestartCurrentDialog   XClearDialogQueue   XFindNonEndingDialogs
XDebugAddHelloDialogsToQueue TargetUID DialogsCount   XDialogFontSizeAnswer InTextSize   XDialogFontSizeSubtitle InTextSize
XAddNotesById InNotePrototypeID   XAddAllNotes   XAddPDATutorialsBySID InPDATutorialPrototypeSID   XTestPDA
XShowHUD bIsShow   XToggleHUDElements ElementsToHide   XHideAllWidget  XShowAllWidget   XHideCompass  XShowCompass
XShowCompassAngle bEnabled   XHideGameDataAndTime  XShowGameDataAndTime   XSetFov FOV   XToggleCustomFov bEnable
XSetCameraShakeScale NewScale   XEnableCinematicMode  XDisableCinematicMode   XPlayVideo Path   XShowIntroductionLogo
XShowPopup ButtonsNum   XShowPopupAttentionIcon   XShowPopupBrokenIcon   XShowPopupCurruptedSaveData   XShowPopupDeleteSave
XShowPopupDiscardChanges   XShowPopupExitGame   XShowPopupGameCannotBeSaveNow   XShowPopupNoIcon   XShowPopupNotEnoughSpace
XShowPopupOverwriteCampaignSlot   XShowPopupOverwriteSavedGame   XShowPopupSaveIcon   XShowPopupSaveSettings
XShowPopupSaveSettinsRestart   XTestSysNotification   XTestSysNotificationAddAudilog   XTestSysNotificationAddItem
XTestSysNotificationAddMoney   XTestSysNotificationAddStash   XTestSysNotificationDiscoverRegion
XTestSysNotificationInspectArtifact   XTestSysNotificationRemoveItem   XTestSysNotificationRemoveMoney
XChangeLanguage LanguageIndex  XChangeLanguageEN  XChangeLanguageRU   XSetTextLanguage LocaleString   XSetAudioLanguage LocaleString
XInputActionBlock IAName IMCName   XInputActionUnlock IAName IMCName   HideCursorInMouseDrag bHide   XSetCurrentCode InCurrentCode
XSetGamepadNavigationBorderSpeed Speed   XGridNavigationVar InVar   XShowUIDebugInput bEnabled   DebugUIShowTextSize bEnabled
XStartProcPopup  XStopProcPopup  XShowDemoPopup  XSkipInfotopicRefreshCooldown  XChangeCompasMarkers Index
```

## Saves, DLC, achievements, engine
```
XCallQuickSave Angular   XCallQuickLoad Angular   XLoadLastSave   XTriggerAutoSave   XToggleAutoSaveEachFrame   XExportSaves
XGetActiveDLC   XHasDLC FName DLCName   XNewDLCAvailable   XSimulateWaitForProfileSettingUp SetupDuration
XAchievementsAddProgress Name Value   XAchievementsProcessFinishCampaign   XAchievementsResetAll   XAchievementsUpdateDebugAchievement value
XRunEngineCommand Command   XCheckGamedata   XFileExists FilePath   XSaveObjListToFile   XBluePrintSearch   XBeginPlay
XIncreaseEnsuresLimit IncreaseLimit   XTestDangling   XTestST162667   XSetDebugMode   XToggleDebugTool   XToggleLogLoadingProgress
XStartBenchmark CameraHeight CircleRadius InitialPitch InitialYaw BenchRuns bProfileCsv   XStopBenchmark
XInitializeBenchmarkSequence AssetPath AssetName
XStartGSCBackgroundProfiler MsecThreshold RamMBThreshold uInFramesToCaptureOnSpike uInFrameCountToComputeAverage
XShowAnalyticsUserId   XToggleAnalyticsTracking_Player bTracking   XIsHDREnabled   XPrintModelCapacity
```

## Debug draws and toggles
```
XToggleFreeCamera   XSetFreeCameraSpeedMultiplier SpeedMultiplier   XSetXRayMode bEnabled   XToggleShowModels
XShowSpawnDebugInfo true|false   XSetSearchpointDebugState true|false   XHighlightCovers NavMeshAgentName
XHighlightDangerAreas NavMeshAgentName   XDisplayFocusingPlayerEnemiesCount   XToggleDrawAIShootingDebug
XShowProjectileTrajectory bShow   XSetDrawDebugExplosion bDebug DebugTime   XToggleGrenadeDebug FlagValue
XToggleDrawPlayerShootingDebug  XToggleDrawPlayerRecoilDebug  XToggleDrawPlayerDispersionDebug  XToggleDebugBulletDistanceScaling
XToggleDebugAimAssist  XToggleHoldBreathDebug  XToggleDebugPlayerArmorInfo  XToggleShowProtection  XToggleDetailedVitalsStat VitalType
XToggleDrawPlayerStats ValueFontXSizeCoef ValueFontYSizeCoef   XToggleDrawInteractNPCStats ValueFontXSizeCoef ValueFontYSizeCoef
XShowStatProgres bEnabled   XToggleShowPlayerLocation  XToggleShowPlayerLastHeldItem  XToggleShowPlayerRequestedMainHandWeaponType
XToggleShowTriggerCapsuleView   XTogglePhysicalMaterialDebug Distance   XShowMaterial ObjUID MaterialID LODId
XDrawPsyFieldVolumes bInDrawPsyField   XTogglePsyPhantomDebugMode   XTogglePlayerRadiationSphereVisibility
XDisableFrictionForPlayerInBulb bInDrawBulbDebug   XToggleDebugExpulsionAnomaly   XToggleDrawDebugDiamondAnomaly
XToggleDebugDrawOverlapWithAnomalyObjects   XToggleShowLightningBallAnomalyDebugInfo   XToggleDebugLightningBallNavigation
XToggleSoapBubbleDebug   XToggleDebugCodeLock   XSetAkVisualizationRadius NewValue   XToggleAkVisualization Types
XDebugAudioScattererEvents bEnabled DrawTime   XDebugAudioScattererMap bEnabled
```

## Linux / Proton
- The commands are the same under Proton; nothing about them is platform-specific.
- The game log under Proton sits in the prefix (`<prefix>/drive_c/users/steamuser/AppData/Local/Stalker2/Saved/Logs/
  Stalker2.log`, `<prefix>` = `<steam>/steamapps/compatdata/1643320/pfx`) and is just as empty about gameplay and mods.
