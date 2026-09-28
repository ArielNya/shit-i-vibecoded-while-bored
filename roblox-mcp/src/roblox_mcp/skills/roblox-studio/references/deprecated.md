# Deprecated Roblox APIs

Generated from the Engine API reference for Studio 0.740.19.7400931 (creator-docs `0b817b5`) by `scripts/build_api_index.py`. Don't use these in new code; the note says what replaces them when the docs do.

Hidden members and deprecated enum items are left out.

## Classes

| API | Note |
| --- | --- |
| `AccessoryDescription:Puffiness` |  |
| `AdGui:OnAdEvent` | This callback has been deprecated and will never be called. |
| `AdService:ShowVideoAd` | `ShowVideoAd` has been decommissioned and is no longer operational. |
| `AdService:VideoAdClosed` | `VideoAdClosed` has been decommissioned and is no longer operational. |
| `AlignOrientation:PrimaryAxisOnly` | This property is deprecated. Depending on your usage case, set `AlignType` directly to `PrimaryAxisParallel`, `PrimaryAxisPerpendicular` or `PrimaryAxisLookAt` instead. |
| `AnalyticsService:ApiKey` | This property is deprecated. Do not use it for new work. |
| `AnalyticsService:FireCustomEvent` | This deprecated function is a variant of `AnalyticsService:LogCustomEvent()` which should be used instead. |
| `AnalyticsService:FireEvent` | This function has been deprecated in favor of more descriptive methods, including `AnalyticsService:LogCustomEvent()`, `AnalyticsService:LogEconomyEvent()`, and `AnalyticsService:LogProgressionEvent()`. |
| `AnalyticsService:FireInGameEconomyEvent` | This deprecated function is a variant of `AnalyticsService:LogEconomyEvent()` which should be used instead. |
| `AnalyticsService:FireLogEvent` | This method is deprecated. Do not use it for new work. |
| `AnalyticsService:FirePlayerProgressionEvent` | This deprecated function is a variant of `AnalyticsService:LogProgressionEvent()` which should be used instead. |
| `AnimationClipProvider:GetAnimationClip` | This function is deprecated and can lead to the game freezing until the animation is loaded. Developers are recommended to use `GetAnimationClipAsync` instead. |
| `AnimationClipProvider:GetAnimationClipById` | This function is deprecated and can lead to the game freezing until the animation is loaded. Developers are recommended to use `GetAnimationClipAsync` instead. |
| `AnimationClipProvider:GetAnimations` |  |
| `AnimationController:AnimationPlayed` |  |
| `AnimationController:GetPlayingAnimationTracks` |  |
| `AnimationController:LoadAnimation` | This function is deprecated in favor of using `Animator:LoadAnimation()` directly (the `Animator` may be created while editing or at runtime). |
| `AnimationTrack:KeyframeReached` | This event has been superseded by the `AnimationTrack:GetMarkerReachedSignal()` method. |
| `AssetService:CreatePlaceInPlayerInventoryAsync` | This method has been removed and is no longer functional. |
| `AssetService:GetAssetIdsForPackage` | Use `GetAssetIdsForPackageAsync()` instead. |
| `AssetService:GetCreatorAssetID` | This item is deprecated and no longer functions correctly. Do not use it for new work. |
| `AssetService:SearchAudio` | Use `SearchAudioAsync()` instead. |
| `Attachment:GetAxis` | This method is deprecated and should not be used in new work. |
| `Attachment:GetSecondaryAxis` | This method is deprecated and should not be used in new work. |
| `Attachment:SetAxis` | This method is deprecated and should not be used in new work. |
| `Attachment:SetSecondaryAxis` | This method is deprecated and should not be used in new work. |
| `AudioEmitter:SimulationFidelity` |  |
| `AudioListener:SimulationFidelity` |  |
| `AudioSearchParams:AudioSubtype` | Use `AudioSubType` instead. |
| `AvatarCreationService:AvatarModerationCompleted` | This event is deprecated. Use `AvatarCreationService.AvatarOutfitModerationCompleted` instead; the replacement event supports avatar outfits and other in-experience-created outfit types. |
| `AvatarEditorService:CheckApplyDefaultClothing` |  |
| `AvatarEditorService:ConformToAvatarRules` |  |
| `AvatarEditorService:GetAvatarRules` |  |
| `AvatarEditorService:GetBatchItemDetails` |  |
| `AvatarEditorService:GetFavorite` |  |
| `AvatarEditorService:GetInventory` |  |
| `AvatarEditorService:GetItemDetails` |  |
| `AvatarEditorService:GetOutfitDetails` |  |
| `AvatarEditorService:GetOutfits` |  |
| `AvatarEditorService:GetRecommendedAssets` |  |
| `AvatarEditorService:GetRecommendedBundles` |  |
| `AvatarEditorService:SearchCatalog` |  |
| `BadgeService:AwardBadge` | Use `AwardBadgeAsync()` instead. |
| `BadgeService:IsDisabled` | This function is deprecated. Do not use it for new work. Instead, it can be checked by calling BadgeService:GetBadgeInfoAsync() and checking the IsEnabled field. |
| `BadgeService:IsLegal` | This function is deprecated and will always return true. Do not use it for new work. |
| `BadgeService:UserHasBadge` | This method has been superseded by `BadgeService:UserHasBadgeAsync()` which should be used for new work instead. |
| `BasePart:BreakJoints` | This method is deprecated. To break specific joints, iterate over the part's connections using `BasePart:GetJoints()` and call `Instance:Destroy()` on the joints you want to remove. |
| `BasePart:CollisionGroupId` |  |
| `BasePart:GetRenderCFrame` | This item is been deprecated since interpolation is now applied to the `CFrame` directly. Do not use it for new work. |
| `BasePart:GetRootPart` |  |
| `BasePart:LocalSimulationTouched` | This event is deprecated in favor of `BasePart.Touched`. |
| `BasePart:MakeJoints` | SurfaceType based joining is deprecated, do not use MakeJoints for new projects. `WeldConstraints` and `HingeConstraints` should be used instead. |
| `BasePart:OutfitChanged` | This event is deprecated. Do not use it for new work. |
| `BasePart:SpecificGravity` | This item is deprecated. See `BasePart.CustomPhysicalProperties` to see how to configure the physical properties of BaseParts. Do not use it for new work. |
| `BasePart:StoppedTouching` | This event is deprecated in favor of `BasePart.TouchEnded`, which should be used instead. |
| `BasePart:breakJoints` | This deprecated function is a variant of `BasePart:BreakJoints()` which should be used instead. |
| `BasePart:brickColor` | This deprecated property is an old Camel Case variant of the Pascal Case `BasePart.BrickColor`, which should be used instead. |
| `BasePart:getMass` | This Camel Case property has been deprecated in favor of its Pascal Case variant, `BasePart:GetMass()`. |
| `BasePart:makeJoints` | This deprecated function is a variant of `BasePart:MakeJoints()` which should be used instead. |
| `BasePart:resize` | This deprecated function is a variant of `BasePart:Resize()` which should be used instead. |
| `BaseScript:LinkedSource` | This property is now replaced by [packages](https://create.roblox.com/docs/projects/assets/packages) which has greater functionality. |
| `BevelMesh` | This object serves no purpose other than being an abstract class that `BlockMesh` and `CylinderMesh` inherit from. Note non-character beveled parts were removed in 2013. Developers looking for beveled edges are required to use either `UnionOperations` or `MeshParts`. |
| `BillboardGui:DistanceLowerLimit` |  |
| `BillboardGui:DistanceUpperLimit` |  |
| `BodyAngularVelocity` | This object is deprecated and should not be used for new work. Use `AngularVelocity` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BodyForce` | This object is deprecated and should not be used for new work. Use `VectorForce` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BodyGyro` | This object is deprecated and should not be used for new work. Use `AlignOrientation` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BodyMover` | This class has been deprecated. See the [mover constraints](https://create.roblox.com/docs/physics/mover-constraints) article for an overview of `BodyMover` replacements, as well as the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BodyPosition` | This object is deprecated and should not be used for new work. Use `AlignPosition` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BodyThrust` | This object is deprecated and should not be used for new work. Use `VectorForce` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BodyVelocity` | This object is deprecated and should not be used for new work. Use `LinearVelocity` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `BoolValue:changed` | This event is a deprecated variant of `BoolValue.Changed` which should be used instead. |
| `BrickColorValue:changed` | This event is a deprecated variant of `BrickColorValue.Changed` which should be used instead. |
| `CFrameValue:changed` | This event is a deprecated variant of `CFrameValue.Changed` which should be used instead. |
| `Camera:GetLargestCutoffDistance` | This method is deprecated. Do not use it for new work. |
| `Camera:GetPanSpeed` | This method has been deprecated and no longer works. It should not be used in new work. |
| `Camera:GetRoll` | This method has been deprecated. |
| `Camera:GetTiltSpeed` | This method has been deprecated and no longer works. |
| `Camera:Interpolate` | This method has been deprecated. Instead use `TweenService` to smoothly animate the `Camera`, see the code snippets below for an example. |
| `Camera:InterpolationFinished` | This event has been deprecated. Instead use `TweenService` to smoothly animate the `Camera`. |
| `Camera:PanUnits` | This method was used for legacy camera controls and has since been deprecated. Do not use in new work. |
| `Camera:SetCameraPanMode` | This method has been deprecated and should not be used in new work. |
| `Camera:SetRoll` | This method has been deprecated. Instead use the `CFrame` property to 'roll' the `Camera`. |
| `Camera:TiltUnits` | This method was used for legacy camera controls and has been deprecated. Do not use in new work. |
| `Camera:focus` | This property is a deprecated variant of `Focus` which should be used instead. |
| `CaptureService:CaptureSaved` | This event has been superseded by the `UserCaptureSaved` event. |
| `Chat` | This class is deprecated. Use `TextChatService` instead. |
| `ClickDetector:mouseClick` | This deprecated event is a variant of `ClickDetector.MouseClick`, which should be used instead. |
| `CollectionService:GetCollection` | This item has been superseded by a `CollectionService` tagging method. The equivalent function using the new method is `CollectionService:GetTagged()` which should be used in new work. |
| `CollectionService:ItemAdded` | This item has been superseded by a `CollectionService` tagging method. There is currently no means of checking when a tag is added. |
| `CollectionService:ItemRemoved` | This item has been superseded by a `CollectionService` tagging method. There is currently no means of checking when a tag is removed. |
| `Color3Value:changed` | This deprecated event is a variant of `Color3Value.Changed` which should be used instead. |
| `Constraint:GetDebugAppliedForce` | This method should not be used in new work. |
| `Constraint:GetDebugAppliedTorque` | This method should not be used in new work. |
| `ContentProvider:Preload` | This item has been superseded by `ContentProvider:PreloadAsync()` which should be used in all new work. |
| `ContextActionService:BindActionToInputTypes` | This item has been superseded by `ContextActionService:BindAction()` which should be used in all new work. |
| `Controller:bindButton` | This function is a deprecated variant of `Controller:BindButton()` which should be used instead. |
| `Controller:getButton` | This function is a deprecated variant of `Controller:GetButton()` which should be used instead. |
| `CustomEvent` | `CustomEvents` have been superseded by `BindableEvents` and should not be used in new work. |
| `CustomEventReceiver` | `CustomEvents` have been superseded by `BindableEvents` and should not be used in new work. |
| `CylinderMesh` | This class is deprecated, and `CylinderMeshes` are no longer supported. Do not use it for new work. |
| `CylindricalConstraint:SoftlockAngularServoUponReachingTarget` | This property should not be used in new work. |
| `DataModel:AllowedGearTypeChanged` | This item is deprecated . Do not use it for new work. |
| `DataModel:GearGenreSetting` | This property is deprecated and is no longer functional. It should not be used. |
| `DataModel:Genre` | This property is deprecated and is no longer functional. It should not be used. |
| `DataModel:GetMessage` | This item is deprecated since the system was phased out a very long time ago, and recently the APIs for setting this message were removed. |
| `DataModel:GetObjects` | This item is deprecated. Do not use it for new work. |
| `DataModel:GetRemoteBuildMode` | This item is deprecated. Use `RunService:IsServer()` to see if your code is running on the server. |
| `DataModel:IsGearTypeAllowed` | This property is deprecated and is no longer functional. It should not be used. |
| `DataModel:ItemChanged` | This function has been superseded by `Object.Changed`, which should be used in new work instead. |
| `DataModel:OnClose` | This function is deprecated. It is recommended to use `DataModel:BindToClose()` instead. |
| `DataModel:SavePlace` | This item is deprecated. Do not use it for new work. |
| `DataModel:lighting` | This item has been superseded by `game:GetService("Lighting")`, which should be used instead. |
| `DataModel:workspace` | This deprecated property is a variant of `DataModel.Workspace` which should be used instead. |
| `DataStore:RemoveVersionAsync` | This method is deprecated. Do not use it for new work. |
| `Debris:MaxItems` | This property is deprecated and should not be used in new work. |
| `Debris:addItem` | This function is a deprecated variant of `Debris:AddItem()` which should be used instead. |
| `Decal:Shiny` | This non-functional property is deprecated and should not be used in new work. |
| `Decal:Specular` | This property no longer functions correctly and is deprecated. It should not be used in new work. |
| `Decal:Texture` | This property has been deprecated. Use `ColorMapContent` for future work. |
| `Decal:TextureContent` | This property has been deprecated. Use `ColorMapContent` for future work. |
| `DoubleConstrainedValue` | The DoubleConstrainedValue object has been deprecated as developers can now use the `math.clamp()` function to constrain values. |
| `Dragger` | This class has been deprecated, as it does not work well with `FilteringEnabled`, and should not be used in new work. |
| `EditableMesh:GetFacesWithAttribute` | This method is deprecated. Do not use it for new work. |
| `EditableMesh:GetVerticesWithAttribute` | This method is deprecated. Do not use it for new work. |
| `Fire:size` | This property is a deprecated variant of `Fire.Size` which should be used instead. |
| `Flag` | The `Flag` and `FlagStand` objects were created to allow developers to make 'capture the flag' style games quickly. However they have been deprecated and developers are advised to design their own systems which will be more flexible and reliable. |
| `FlagStand` | The FlagStand and Flag are deprecated objects that were used to make 'capture the flag' style games. Developers are advised to design their own systems which will be more flexible and reliable. |
| `FlagStandService` | This internal service was once responsible for handling the now deprecated `FlagStand` and `Flag` objects, and is now deprecated. |
| `FloorWire` | The FloorWire object has been deprecated and should not be used in new work. |
| `FormFactorPart` | This class has been deprecated along with the `FormFactorPart.FormFactor` property. |
| `FunctionalTest` | FunctionalTest has been deprecated, developers are advised to use `TestService` instead. |
| `GamePassService:PlayerHasPass` |  |
| `GameSettings:VideoCaptureEnabled` | This property is deprecated. Do not use it for new work. |
| `GenerationService:GenerateMeshAsync` | This method is scheduled for future deprecation. Explore `GenerateModelAsync()` as a newer method. |
| `GlobalDataStore:OnUpdate` | This function has been deprecated and should not be used in new work. You can use the `Cross Server Messaging Service` to publish and subscribe to topics to receive near real-time updates, completely replacing the need for this function. |
| `Glue` | This joint type has been deprecated and should not be used in new work. |
| `GuiMain` | This deprecated class is the original name of the `ScreenGui`. It functions identically to the ScreenGui, and should not be used. |
| `GuiObject:DragBegin` | This property is deprecated. Use `UIDragDetector` instead, as it supports more input types and can be better customized. |
| `GuiObject:DragStopped` | This property is deprecated. Use `UIDragDetector` instead, as it supports more input types and can be better customized. |
| `GuiObject:Draggable` | This property is deprecated. Use `UIDragDetector` instead, as it supports more input types and can be better customized. |
| `GuiObject:TweenPosition` | This function is deprecated in favor of using `TweenService`, which allows for better customization using an object-oriented and event-based approach. - The `easingDirection`, `easingStyle`, and `time` parameters are handled by a `TweenInfo` - The `override` parameter is no longer relevant; tweens always override previous tweens on the same property. - The `callback` parameter is better suited by the `Tween.Completed` event. The `Enum.PlaybackState` enum passed by that event provides a more detailed description of the tween's completion state. |
| `GuiObject:TweenSize` | This function is deprecated in favor of using `TweenService`, which allows for better customization using an object-oriented and event-based approach. - The `easingDirection`, `easingStyle`, and `time` parameters are handled by a `TweenInfo` - The `override` parameter is no longer relevant; tweens always override previous tweens on the same property. - The `callback` parameter is better suited by the `Tween.Completed` event. The `Enum.PlaybackState` enum passed by that event provides a more detailed description of the tween's completion state. |
| `GuiObject:TweenSizeAndPosition` | This function is deprecated in favor of using `TweenService`, which allows for better customization using an object-oriented and event-based approach. - The `easingDirection`, `easingStyle`, and `time` parameters are handled by a `TweenInfo` - The `override` parameter is no longer relevant; tweens always override previous tweens on the same property. - The `callback` parameter is better suited by the `Tween.Completed` event. The `Enum.PlaybackState` enum passed by that event provides a more detailed description of the tween's completion state. |
| `GuiService:AddSelectionParent` |  |
| `GuiService:AddSelectionTuple` |  |
| `GuiService:IsModalDialog` | This item is deprecated. Do not use it for new work. |
| `GuiService:IsTenFootInterface` | This method has been superseded by the `ViewportDisplaySize` property which represents the internally‑categorized rendering size of the viewport. |
| `GuiService:IsWindows` | This item is deprecated. Do not use it for new work. |
| `GuiService:RemoveSelectionGroup` |  |
| `HapticService` | This service has been superseded by `HapticEffect`, a newer instance that supports multiple haptic effect types, looped effects, and customizable haptics. |
| `Hat` | This class has been superseded by the `Accessory` class. Do not use it for new work. |
| `HingeConstraint:SoftlockServoUponReachingTarget` | This property should not be used in new work. |
| `Hint` | With the introduction of Roblox's GUI features hints have been deprecated and `TextLabels` should be used instead for new work. The `TextLabel` object offers a wide range of features for displaying and customizing text that hints do not. |
| `Hole` | A Hole is an unused type of surface joint. It should not be used in new work. |
| `Hopper` | `Hopper` has been replaced by `StarterPack` and should not be used in new work. |
| `HopperBin` | This deprecated class has been replaced by `Tool`. Please use Tool for new work instead. |
| `Humanoid:AddCustomStatus` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:AddStatus` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:AnimationPlayed` |  |
| `Humanoid:ApplyDescription` | This method has been superseded by `ApplyDescriptionAsync()`. |
| `Humanoid:ApplyDescriptionReset` | This method has been superseded by `ApplyDescriptionResetAsync()`. |
| `Humanoid:CollisionType` |  |
| `Humanoid:CustomStatusAdded` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:CustomStatusRemoved` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:GetPlayingAnimationTracks` |  |
| `Humanoid:GetStatuses` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:HasCustomStatus` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:HasStatus` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:LoadAnimation` | This function is deprecated in favor of using `Animator:LoadAnimation()` directly (the `Animator` may be created while editing or at runtime). |
| `Humanoid:PlayEmote` | This method has been superseded by `PlayEmoteAsync()`. |
| `Humanoid:RemoveCustomStatus` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:RemoveStatus` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:StatusAdded` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:StatusRemoved` | This item is deprecated, as it was a part of the unfinished RbxStatus library which would have allowed you to add conditions to a Humanoid. Do not use it for new work. |
| `Humanoid:loadAnimation` | This deprecated method is a variant of `Humanoid:LoadAnimation()`. `Animator:LoadAnimation()` should be used instead. |
| `Humanoid:maxHealth` | This deprecated property is a variant of `Humanoid.MaxHealth` which should be used instead. |
| `Humanoid:takeDamage` | This deprecated method is a variant of `Humanoid:TakeDamage()`, which should be used instead. |
| `InputAction:Fire` | Use `InputBinding:Fire()` with a `Scriptable` binding instead. |
| `InsertService:AllowInsertFreeModels` | This item was never released. Do not use it in new work. |
| `InsertService:ApproveAssetId` | This item is deprecated. Do not use it for new work. |
| `InsertService:ApproveAssetVersionId` | This item is deprecated. Do not use it for new work. |
| `InsertService:GetBaseCategories` | This item is deprecated. Do not use it for new work. |
| `InsertService:GetBaseSets` | [Sets have been removed](https://devforum.roblox.com/t/sunsetting-sets/189402) from Roblox. |
| `InsertService:GetCollection` | [Sets have been removed](https://devforum.roblox.com/t/sunsetting-sets/189402) from Roblox. |
| `InsertService:GetFreeDecals` | Use `GetFreeDecalsAsync()` instead. |
| `InsertService:GetFreeModels` | Use `GetFreeModelsAsync()` instead. |
| `InsertService:GetUserCategories` | This item is deprecated. Do not use it for new work. |
| `InsertService:GetUserSets` | [Sets have been removed](https://devforum.roblox.com/t/sunsetting-sets/189402) from Roblox. |
| `InsertService:Insert` | This function has been superseded by `InsertService:LoadAsset()` which should be used in all new work. |
| `InsertService:loadAsset` | This function is a deprecated variant of `InsertService:LoadAsset()` which should be used instead. |
| `Instance:Remove` | This item is deprecated in favor of `Instance:Destroy()` and `Instance:ClearAllChildren()`. If you must remove an object from the game, and wish to use the object later, set its `Parent` property to `nil` instead of using this method. |
| `Instance:childAdded` | This deprecated event is a variant of `Instance.ChildAdded` which should be used instead. |
| `Instance:children` | This item has been superseded by `Instance:GetChildren()` which should be used in all new work. |
| `Instance:clone` | This deprecated function is a variant of `Instance:Clone()` which should be used instead. |
| `Instance:destroy` | This deprecated function is a variant of `Instance:Destroy()` which should be used instead. |
| `Instance:findFirstChild` | This deprecated function is a variant of `Instance:FindFirstChild()` which should be used instead. |
| `Instance:getChildren` | This deprecated function is a variant of `Instance:GetChildren()` which should be used instead. |
| `Instance:isDescendantOf` | This deprecated function is a variant of `Instance:IsDescendantOf()` which should be used instead. |
| `Instance:remove` | This deprecated function is a variant of `Instance:Remove()` which has also been deprecated. Neither function should be used in new work. |
| `IntConstrainedValue` | The IntConstrainedValue object has been deprecated as developers can now use the `math.clamp()` function to constrain values. |
| `IntValue:changed` | This deprecated event is a variant of `IntValue.Changed` which should be used instead. |
| `JointsService` | This service has been deprecated in favor of [constraints](https://create.roblox.com/docs/physics/mechanical-constraints) which should be used for surface connections instead |
| `KeyframeSequenceProvider` | This service is deprecated and does not support the newer `AnimationClip`. It's recommended to use `AnimationClipProvider` instead. |
| `LayerCollector:GetLayoutNodeTree` | This method should not be used for new work. |
| `Lighting:GetMoonPhase` | There is currently no way to change the moon's phase, and thus this method should not be used. |
| `Lighting:Outlines` | This item is no longer supported as the outlines feature was removed from the Roblox platform. |
| `Lighting:ShadowColor` | This item is deprecated and has no current functionality. Do not use it for new work. |
| `Lighting:Technology` | This property has been superseded by `LightingStyle` which determines the artistic intent behind lighting, and `PrioritizeLightingQuality` which indicates whether you prefer lighting/shading quality or view distance to scale down first. |
| `Lighting:getMinutesAfterMidnight` | This method is a deprecated variant of `Lighting:GetMinutesAfterMidnight()` which should be used instead. |
| `Lighting:setMinutesAfterMidnight` | This method is a deprecated variant of `Lighting:SetMinutesAfterMidnight()` which should be used instead. |
| `LocalizationService:GetTranslatorForPlayer` | This function has been deprecated by `LocalizationService:GetTranslatorForPlayerAsync()`, which functions similarly except that it yields until the cloud table has loaded. Please use it in new work instead. |
| `LocalizationTable:GetContents` | This item has been superseded by `LocalizationTable:GetEntries()` which should be used in all new work. |
| `LocalizationTable:GetString` | This item has been superseded by `LocalizationTable:GetTranslator()` which should be used in all new work. |
| `LocalizationTable:RemoveKey` | This item has been superseded by `LocalizationTable:RemoveEntry()` which should be used in all new work |
| `LocalizationTable:SetContents` | This item has been superseded by `LocalizationTable:SetEntries()` which should be used in all new work |
| `LocalizationTable:SetEntry` | This item has been superseded by `LocalizationTable:SetEntries()` which should be used in all new work. |
| `ManualGlue` | Deprecated. |
| `ManualSurfaceJointInstance` | Deprecated. |
| `ManualWeld` | Deprecated. |
| `MarketplaceService:GetProductInfo` | This method has been superseded by `GetProductInfoAsync()`. |
| `MarketplaceService:PlayerOwnsAsset` | This method has been superseded by `PlayerOwnsAssetAsync()`. |
| `MarketplaceService:PlayerOwnsBundle` | This method has been superseded by `PlayerOwnsBundleAsync()`. |
| `MarketplaceService:PromptPremiumPurchase` | This method has been superseded by `PromptRobloxSubscriptionPurchase()`. |
| `Message` | With the introduction of Roblox's GUI features hints have been deprecated and `TextLabels` should be used instead for new work. The `TextLabel` object offers a wide range of features for displaying and customizing text that messages do not. |
| `Model:BreakJoints` |  |
| `Model:GetModelCFrame` | This function has been deprecated as it did not provide reliable results. You can instead use `Model:GetPrimaryPartCFrame()` to retrieve the `CFrame` of the model's primary part. |
| `Model:GetModelSize` | This item is deprecated. Do not use it for new work. Developers can instead use `Model.GetExtentsSize`. |
| `Model:GetPrimaryPartCFrame` |  |
| `Model:MakeJoints` | This joint type has been deprecated. Don't use it for new work. Use `WeldConstraints` and `HingeConstraints` instead. |
| `Model:ResetOrientationToIdentity` | This function has been deprecated; it remains to prevent legacy scripts from throwing errors, but it does nothing when called. |
| `Model:SetIdentityOrientation` | This function has been deprecated; it remains to prevent legacy scripts from throwing errors, but it does nothing when called. |
| `Model:SetPrimaryPartCFrame` |  |
| `Model:breakJoints` | This deprecated function is a variant of `Model:BreakJoints()` which should be used instead. |
| `Model:makeJoints` | This deprecated function is a variant of `Model:MakeJoints()` which should be used instead. |
| `Model:move` | This item has been superseded by `Model:MoveTo()` which should be used in all new work |
| `Model:moveTo` | This deprecated function is a variant of `Model:MoveTo()` which should be used instead. |
| `ModuleScript:LinkedSource` | This property is now replaced by [packages](https://create.roblox.com/docs/projects/assets/packages) which has greater functionality. |
| `MotorFeature` | A MotorFeature is an unused type of surface joint. It should not be used for new work. |
| `Mouse:KeyDown` | Mouse events have been superseded by `UserInputService` which should be used in all new work. |
| `Mouse:KeyUp` | Mouse events have been superseded by `UserInputService` which should be used in all new work. |
| `Mouse:keyDown` | This event is a deprecated variant of `Mouse.KeyDown` which has also been deprecated. Neither event should be used in new work. |
| `Mouse:target` | This property is a deprecated variant of `Mouse.Target` which should be used instead. |
| `NumberValue:changed` | This event is a deprecated variant of `NumberValue.Changed` which should be used instead. |
| `Object:className` | This deprecated property is a variant of `Object.ClassName` which should be used instead. |
| `Object:isA` | This deprecated function is a variant of `Object:IsA()` which should be used instead. |
| `ObjectValue:changed` | This event is a deprecated variant of `ObjectValue.Changed` which should be used instead. |
| `OpenCloudApiV1` | This class is deprecated and should not be used for new work. Use `HttpService` instead and see the [In-experience HTTP requests guide](https://create.roblox.com/docs/cloud-services/http-service). |
| `OpenCloudService` | This class is deprecated and should not be used for new work. Use `HttpService` instead and see the [In-experience HTTP requests guide](https://create.roblox.com/docs/cloud-services/http-service). |
| `ParticleEmitter:VelocitySpread` | This property has been superseded by `ParticleEmitter.SpreadAngle` which should be used in all new work. |
| `Path:CheckOcclusionAsync` | This function has been superseded by the `Blocked` event which you can connect to a `Path` object and should be used instead. This lets you detect if the path becomes blocked at any time during its existence. |
| `Path:GetPointCoordinates` | This item has been superseded by `GetWaypoints()` which should be used in all new work instead. |
| `PathfindingService:ComputeRawPathAsync` | This item has been superseded by `PathfindingService:FindPathAsync()` which should be used in all new work instead. |
| `PathfindingService:ComputeSmoothPathAsync` | This item has been superseded by `PathfindingService:FindPathAsync()` which should be used in all new work instead. |
| `PathfindingService:EmptyCutoff` | This property is deprecated, since the legacy pathfinding system using it has since been removed. Do not use it for new work. |
| `PathfindingService:FindPathAsync` | This function has been superseded by the sequential method of calling `PathfindingService:CreatePath()` followed by `Path`. This lets you create a `Path` object using various custom parameters and then compute or re-compute a path on the same object if any dynamic changes within the place block the path. |
| `PhysicsService` | This service has been deprecated in favor of per-world collision group configuration through `WorldRoot` which should be used for collision group management. Existing `PhysicsService` calls will forward to `Workspace`. |
| `Plane` | Deprecated. |
| `Platform` | Historically a form of `Seat` that wouldn't place the player in a sitting pose. This object is no longer create-able and cannot be used by developers. |
| `Player:CharacterAppearance` | This item is deprecated. Do not use it for new work. |
| `Player:GetFriendsOnline` | This method has been superseded by `GetFriendsOnlineAsync()`. |
| `Player:GetRankInGroup` | This method has been superseded by `GetRankInGroupAsync()`. |
| `Player:GetRankInGroupAsync` | This method returns only the rank value of the member's highest public role. Use `GroupService:GetRolesInGroupAsync()` instead, which returns all public roles. |
| `Player:GetRoleInGroup` | This method has been superseded by `GetRoleInGroup()`. |
| `Player:GetRoleInGroupAsync` | This method returns only the member's highest public role. Use `GroupService:GetRolesInGroupAsync()` instead, which returns all public roles. |
| `Player:IsBestFriendsWith` | This function is obsolete because the "best friends" feature was removed. Use `Player:IsFriendsWithAsync()` instead. |
| `Player:IsFriendsWith` | This method has been superseded by the `Player:IsFriendsWithAsync()` method which should be used for new work. |
| `Player:IsInGroup` | This method has been superseded by `IsInGroupAsync()`. |
| `Player:LoadBoolean` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:LoadCharacter` | This method has been superseded by `LoadCharacterAsync()`. |
| `Player:LoadCharacterAppearance` | This method is deprecated. Do not use it for new work. |
| `Player:LoadCharacterWithHumanoidDescription` | This method has been superseded by `LoadCharacterWithHumanoidDescriptionAsync()`. |
| `Player:LoadInstance` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:LoadNumber` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:LoadString` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:MembershipType` | This property is deprecated. Use `Player.HasRobloxSubscription` to check whether a player has an active Roblox subscription. |
| `Player:SaveBoolean` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:SaveInstance` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:SaveNumber` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:SaveString` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:WaitForDataReady` | This item is deprecated, as it may have been used for a now obsolete data persistence method. Please save and load player data using `DataStoreService` for new work. |
| `Player:isFriendsWith` | This method has been superseded by the `Player:IsFriendsWithAsync()` method which should be used for new work. |
| `Player:loadBoolean` | This deprecated function is a variant of `Player:LoadBoolean()` which has also been deprecated. Neither function should be used in new work. |
| `Player:loadInstance` | This deprecated function is a variant of `Player:LoadInstance()` which has also been deprecated. Neither function should be used in new work. |
| `Player:loadNumber` | This deprecated function is a variant of `Player:LoadNumber()` which has also been deprecated. Neither function should be used in new work. |
| `Player:loadString` | This function is a deprecated variant of `Player:LoadString()` which has also been deprecated. Neither function should be used in new work. |
| `Player:saveBoolean` | This function is a deprecated variant of `Player:SaveBoolean()` which has also been deprecated. Neither function should be used in new work. |
| `Player:saveInstance` | This function is a deprecated variant of `Player:SaveInstance()` which has also been deprecated. Neither function should be used in new work. |
| `Player:saveNumber` | This function is a deprecated variant of `Player:SaveNumber()` which has also been deprecated. Neither function should be used in new work. |
| `Player:saveString` | This function is a deprecated variant of `Player:SaveString()` which has also been deprecated. Neither function should be used in new work. |
| `Player:userId` | This property is a deprecated variant of `Player.UserId` which should be used instead. |
| `Player:waitForDataReady` | This function is a deprecated variant of `Player:WaitForDataReady()` which has also been deprecated. Neither function should be used in new work. |
| `PlayerGui:GetTopbarTransparency` |  |
| `PlayerGui:SetTopbarTransparency` |  |
| `PlayerGui:TopbarTransparencyChangedSignal` |  |
| `Players:CreateHumanoidModelFromDescription` | This method has been superseded by `CreateHumanoidModelFromDescriptionAsync()`. |
| `Players:CreateHumanoidModelFromUserId` | This method has been superseded by `CreateHumanoidModelFromUserIdAsync()`. |
| `Players:GetCharacterAppearanceAsync` | This method is deprecated. Do not use it for new work. |
| `Players:GetHumanoidDescriptionFromOutfitId` | This method has been superseded by `GetHumanoidDescriptionFromOutfitIdAsync()`. |
| `Players:GetHumanoidDescriptionFromUserId` | This method has been superseded by `GetHumanoidDescriptionFromUserIdAsync()`. |
| `Players:NumPlayers` | This item is deprecated. Instead, of using this item, you should count the number of players returned by `Players:GetPlayers()`. |
| `Players:getPlayers` | This function is a deprecated variant of `Players:GetPlayers()` which should be used instead. |
| `Players:playerFromCharacter` | This function is a deprecated variant of `Players:GetPlayerFromCharacter()` which should be used in new work. |
| `Players:players` | This item has been superseded by `Players:GetPlayers()` which should be used in all new work. |
| `Plugin:CreateDockWidgetPluginGui` | This method has been superseded by `CreateDockWidgetPluginGuiAsync()`. |
| `Plugin:GetStudioUserId` |  |
| `Plugin:ImportFbxAnimation` |  |
| `Plugin:ImportFbxRig` | This method has been superseded by `ImportFbxRigAsync()`. |
| `Plugin:OpenScript` |  |
| `Plugin:PromptSaveSelection` | This method has been superseded by `PromptSaveSelectionAsync()`. |
| `PluginManager:CreatePlugin` | The steps to create a plugin have changed. To learn more, see `Plugin`. |
| `PluginManagerInterface:CreatePlugin` | The steps to create a plugin have changed. To learn more, see `Plugin`. |
| `PointsService` | This class was once used to control an ancient achievement system since removed and deprecated. It and its members should not be used in new work. |
| `Pose:MaskWeight` | This property is deprecated. Use the `AnimationTrack:AdjustWeight()` function when blending multiple animations. |
| `PoseBase:Weight` | This property is deprecated. Use the `AnimationTrack:AdjustWeight()` function when blending multiple animations. |
| `RayValue:changed` | This event is a deprecated variant of `RayValue.Changed` which should be used instead. |
| `RocketPropulsion` | This object is deprecated and should not be used for new work. Use `LineForce` instead, and see the [legacy conversion notes](https://create.roblox.com/docs/physics/mover-constraints#legacy-mover-conversion). |
| `Rotate` | This class works alongside the deprecated `Enum.SurfaceType` and should not be used for future work; use `HingeConstraint` instead. |
| `RotateP` | This class works alongside the deprecated `Enum.SurfaceType` and should not be used for future work; use `HingeConstraint` instead. |
| `RotateV` | This class works alongside the deprecated `Enum.SurfaceType` and should not be used for future work; use `HingeConstraint` instead. |
| `RunService:Reset` | This item is deprecated and should not be used in new work. |
| `SelectionPartLasso` | SelectionPartLasso has been deprecated. Developers are advised to use the `Beam` object instead. |
| `SelectionPointLasso` | The SelectionPointLasso class is deprecated. It should not be used for new work. |
| `SensorBase:Sense` | This method should not be used in new work. |
| `ServiceProvider:getService` | This deprecated function is a variant of `ServiceProvider:GetService()` which should be used instead. |
| `ServiceProvider:service` | This item has been superseded by `ServiceProvider:GetService()` which should be used in all new work. |
| `SkateboardPlatform` | The SkateboardPlatform object has been deprecated and is no longer supported by Roblox. Developers looking to create skateboards or similar vehicles are advised to program their own systems. Additionally, the `VehicleSeat` object can be used to quickly create simple vehicles. |
| `Skin` | This object has been deprecated and superseded by `BodyColors`. The Skin object does not function on R15 characters and should not be used for new work. `BodyColors` functions with R15 characters and allows the colors of each limb to be set individually. |
| `SlidingBallConstraint:SoftlockServoUponReachingTarget` | This property should not be used in new work. |
| `Snap` | Deprecated. |
| `SocialService:PromptLinkSharing` | Use `PromptLinkSharingAsync()` instead. |
| `Sound:EmitterSize` | This property has deprecated in favor of `Sound.RollOffMinDistance` and `Sound.RollOffMaxDistance` which should be used instead in new work. |
| `Sound:MaxDistance` | This property has deprecated in favor of `Sound.RollOffMinDistance` and `Sound.RollOffMaxDistance` which should be used instead in new work. |
| `Sound:MinDistance` | MinDistance has been superseded by `Sound.EmitterSize`, whose name better describes this properties behavior. |
| `Sound:Pitch` | This property has been deprecated in favor of `Sound.PlaybackSpeed` whose name suits the behavior better. |
| `Sound:isPlaying` | This deprecated property is a variant of `Sound.IsPlaying` which should be used instead. |
| `Sound:pause` | This deprecated function is a variant of `Sound:Pause()` which should be used instead. |
| `Sound:play` | This deprecated function is a variant of `Sound:Play()` which should be used instead. |
| `Sound:stop` | This deprecated function is a variant of `Sound:Stop()` which should be used instead. |
| `StarterGui:ResetPlayerGuiOnSpawn` | This property is deprecated. Use `LayerCollector.ResetOnSpawn` to control the resetting behavior for individual `LayerCollector` objects. |
| `Stats:HeartbeatTimeMs` | Use `Stats.HeartbeatTime` instead. |
| `Stats:PhysicsStepTimeMs` | Use `Stats.PhysicsStepTime` instead. |
| `Status` | Status is an unfinished object designed to store custom `Humanoid` statuses. It has been deprecated and should not be used by developers in new work. Developers looking to implement custom `Humanoid` statuses should use [Character Physics Controllers](https://devforum.roblox.com/t/releasing-character-physics-controllers/2623426), as they are written in Luau and are easily extendable. |
| `StringValue:changed` | This deprecated event is a variant of `StringValue.Changed` which should be used instead. |
| `StudioService:DrawConstraintsOnTop` | This property is deprecated; constraints can no longer be drawn "on top" of other objects. |
| `StudioService:PromptImportFile` |  |
| `StudioService:PromptImportFiles` |  |
| `Team:AutoColorCharacters` | This property is deprecated and no longer functions, it should not be used for new work. |
| `Team:Score` | This property is deprecated and should not be used in new work. For more information on how to handle leaderboards and scoring please see [this tutorial](https://create.roblox.com/docs/players/leaderboards). |
| `Teams:RebalanceTeams` | This function has been deprecated and no longer functions correctly. It should not be used. Developers should instead implement their own team sorting systems. |
| `TeleportService:CustomizedTeleportUI` | This item is deprecated since the default message it controls has been removed. Do not use it for new work. |
| `TeleportService:ReserveServer` | Use `ReserveServerAsync()` instead. |
| `TeleportService:Teleport` | Use `TeleportAsync()` for server-side teleports. For client-side teleports, use a `RemoteEvent` to signal the server to call `TeleportAsync()`. For a migration guide, see [Teleport between places](https://create.roblox.com/docs/projects/teleport#migrate-to-secure-teleports). |
| `TeleportService:TeleportPartyAsync` | Use `TeleportAsync()` instead. For a migration guide, see [Teleport between places](https://create.roblox.com/docs/projects/teleport#migrate-to-secure-teleports). |
| `TeleportService:TeleportToPlaceInstance` | Use `TeleportAsync()` instead. For a migration guide, see [Teleport between places](https://create.roblox.com/docs/projects/teleport#migrate-to-secure-teleports). |
| `TeleportService:TeleportToPrivateServer` | Use `TeleportAsync()` instead. For a migration guide, see [Teleport between places](https://create.roblox.com/docs/projects/teleport#migrate-to-secure-teleports). |
| `TeleportService:TeleportToSpawnByName` | Use `TeleportAsync()` instead. For a migration guide, see [Teleport between places](https://create.roblox.com/docs/projects/teleport#migrate-to-secure-teleports). |
| `Terrain:AutowedgeCell` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `Terrain:AutowedgeCells` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `Terrain:ConvertToSmooth` | Since all places now automatically use the new terrain engine, this method is obsolete. |
| `Terrain:GetCell` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `Terrain:GetWaterCell` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `Terrain:IsSmooth` | The legacy terrain engine has been removed, so this property will always be `true`. |
| `Terrain:SetCell` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `Terrain:SetCells` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `Terrain:SetWaterCell` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `TerrainRegion:ConvertToSmooth` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `TerrainRegion:IsSmooth` | This item is a deprecated function of a legacy `Terrain` engine that has been removed. Do not use it for new work. |
| `TestService:Is30FpsThrottleEnabled` | This has been deprecated and directly renamed to `ThrottlePhysicsToRealtime` to better reflect its practical use. |
| `TestService:Run` | Use `RunAsync()` instead. |
| `TextBox:FontSize` | This item has been superseded by `TextBox.TextSize` which should be used in all new work. |
| `TextBox:TextWrap` | This item has been superseded by `TextBox.TextWrapped` which should be used in all new work. |
| `TextButton:FontSize` | This property is deprecated in favor of `TextSize` which is an integer and not an enum and thus offers far more options for sizes. |
| `TextButton:TextWrap` | This item has been superseded by `TextButton.TextWrapped` which should be used in all new work. |
| `TextChatService:ChatVersion` | This property has been deprecated in newly created Studio experiences. `TextChatService` is the only allowed chat system and is automatically enabled. |
| `TextFilterResult:GetChatForUserAsync` | This method is deprecated and returns an empty string. Text filtering pertaining to chat should be done through `TextChatService`, and experiences that do not properly filter player-generated chat text may be subject to moderation. |
| `TextLabel:FontSize` | This property is deprecated in favor of `TextSize` which is an integer and not an enum and thus offers far more options for sizes. |
| `TextLabel:TextWrap` | This property is simply an alias for `TextWrapped`. Use the past-tense version instead. |
| `TextService:FilterAndTranslateStringAsync` | This method is no longer supported and should not be used. All calls return an empty object. |
| `UIGridStyleLayout:ApplyLayout` |  |
| `UIGridStyleLayout:SetCustomSortFunction` | This method is deprecated in favor of using other SortOrder means, such as by Name or LayoutOrder. |
| `UserGameSettings:ControlMode` | This property has been deprecated. You can enable mouse-locked third-person control, or "Shift Lock Mode", through the `Enum.MouseBehavior` in `PlayerScripts:RegisterTouchCameraMovementMode()` and `PlayerScripts:RegisterComputerCameraMovementMode()`. |
| `UserInputService:GetUserCFrame` | Use `VRService:GetUserCFrame()` instead. |
| `UserInputService:ModalEnabled` | This item has been superseded by `GuiService.TouchControlsEnabled` which should be used in all new work. |
| `UserInputService:UserCFrameChanged` | Use `VRService.UserCFrameChanged` instead. |
| `UserInputService:UserHeadCFrame` | This item has been superseded by `UserInputService:GetUserCFrame()` which should be used in all new work. |
| `UserInputService:VREnabled` | This property has been superseded by `VRService.VREnabled` which should be used in all new work. |
| `Vector3Value:changed` | This deprecated event is a variant of `Vector3Value.Changed` which should be used instead. |
| `VehicleSeat:Steer` | This property is no longer replicated and has been deprecated in favor of `SteerFloat` which is a float variant and should be used instead. |
| `VehicleSeat:Throttle` | This property is not longer replicated and has been deprecated in favor of `ThrottleFloat` which is a float variant and should be used instead. |
| `Workspace:BreakJoints` | This method is deprecated. Do not use it for new work. |
| `Workspace:MakeJoints` | This method is deprecated. Do not use it for new work. |
| `WorldRoot:FindPartOnRay` | This function has been deprecated. Use `WorldRoot:Raycast()` along with `RaycastParams` for new work. |
| `WorldRoot:FindPartOnRayWithIgnoreList` | This function has been deprecated. Use `WorldRoot:Raycast()` along with `RaycastParams` for new work. |
| `WorldRoot:FindPartOnRayWithWhitelist` | This function has been deprecated. Use `WorldRoot:Raycast()` along with `RaycastParams` for new work. |
| `WorldRoot:FindPartsInRegion3` | This function has been deprecated. Use `WorldRoot:GetPartBoundsInBox()` along with `OverlapParams` for new work. |
| `WorldRoot:FindPartsInRegion3WithIgnoreList` | This function has been deprecated. Use `WorldRoot:GetPartBoundsInBox()` along with `OverlapParams` for new work. |
| `WorldRoot:FindPartsInRegion3WithWhiteList` | This function has been deprecated. Use `WorldRoot:GetPartBoundsInBox()` along with `OverlapParams` for new work. |
| `WorldRoot:IsRegion3Empty` | This function has been deprecated. Use `WorldRoot:GetPartBoundsInBox()` along with `OverlapParams` for new work. |
| `WorldRoot:IsRegion3EmptyWithIgnoreList` | This function has been deprecated. Use `WorldRoot:GetPartBoundsInBox()` along with `OverlapParams` for new work. |
| `WorldRoot:findPartOnRay` | This deprecated function is a variant of `WorldRoot:FindPartOnRay()` which should be used instead. |
| `WorldRoot:findPartsInRegion3` | This deprecated function is a variant of `WorldRoot:FindPartsInRegion3()` which should be used instead. |
| `WrapLayer:Puffiness` |  |
| `WrapLayer:ShrinkFactor` |  |
| `WrapTarget:Stiffness` |  |

## Globals

| API | Note |
| --- | --- |
| `DebuggerManager` | The `DebuggerManager` is obsolete and serves little to no use case for developers. |
| `collectgarbage` |  |
| `delay` | This method has been superseded by `task.delay()` and should not be used for future work. |
| `elapsedTime` |  |
| `getfenv` | This function allows uncontrolled change of the global/function environment and disables script optimizations. Changes to the environment are not tracked by the script analysis tooling and may result in missing or incorrect warnings. As a replacement, consider using `debug.info()` instead. |
| `printidentity` |  |
| `setfenv` | This function allows uncontrolled change of the global/function environment and disables script optimizations. Changes to the environment are not tracked by the script analysis tooling and may result in missing or incorrect warnings. |
| `spawn` | This method has been superseded by `task.spawn()` and should not be used for future work. |
| `stats` |  |
| `version` |  |
| `wait` | This method has been superseded by `task.wait()` and should not be used for future work. |
| `ypcall` |  |

## Libraries

| API | Note |
| --- | --- |
| `table.foreach` |  |
| `table.foreachi` |  |
| `table.getn` |  |

## Datatypes

| API | Note |
| --- | --- |
| `Color3.toHSV` | This function is functionally equivalent to `Color3:ToHSV()`. |

## Enums

| API | Note |
| --- | --- |
| `BinType` | This deprecated Enum is used by `HopperBin` which has also been deprecated. Neither should be used in new work. |
| `CellBlock` | This enum is deprecated. It used to work with `Terrain:SetCell()` - a function that is no longer supported by the `Terrain` engine. |
| `CellMaterial` | This enum is deprecated. It used to work with the legacy `Terrain` engine to set the material of terrain cells. |
| `CellOrientation` | This enum is deprecated. It used to work with the legacy `Terrain` engine to set the orientation of terrain cells. |
| `CurrencyType` | Tickets have been removed, so this Enum shouldn't need to be used. |
| `FormFactor` | This item is deprecated as parts no longer contain a FormFactor to determine their minimum size. The minimum size of all parts now behaves like "Custom" by default. |
| `GearGenreSetting` | This enum is deprecated as it is used by deprecated properties that are no longer functional. It should not be used. |
| `GearType` | This enum is deprecated because it's used by deprecated properties. Don't use it. |
| `Genre` | Deprecated. |
| `InputType` | This enum is deprecated as it is used by deprecated methods. It should not be used in new work. |
| `PlayerActions` | This enum has been deprecated in favor of `Enum.KeyCode` which is more platform-agnostic and should be used in new work instead. |
| `SaveFilter` | This deprecated enum is used by `DataModel.SavePlace` which has also been deprecated. Neither should be used in new work. |
| `Status` | This enum is deprecated as it was only used by deprecated methods and events. It should not be used in new work. |
| `StreamingPauseMode` | Please use `Workspace.StreamingIntegrityMode` instead. |
| `SurfaceConstraint` | This item is deprecated and is replaced by the `Enum.SurfaceType` enum. |
| `SurfaceType` | **SurfaceType** joining is deprecated, leaving only visual changes on the affected `Part`. It should not be used for future work. |
| `UITheme` | This enum refers to a deprecated setting and should not be used for new work. Use `Studio.Theme` (`StudioTheme`) instead. |
| `WaterDirection` | This item is deprecated. Do not use it for new work. Please see `Terrain` for a list of current function, events, and properties. |
| `WaterForce` | This item is deprecated. Do not use it for new work. Please see `Terrain` for a list of current function, events, and properties. |
